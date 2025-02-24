import os
import logging
import asyncio
from typing import Awaitable, Callable, Optional, Tuple
from autogen_core import CancellationToken
from autogen_ext.models.openai import OpenAIChatCompletionClient
from autogen_agentchat.agents import AssistantAgent, UserProxyAgent
from autogen_agentchat.teams import MagenticOneGroupChat
from tools.ticktick import TaskManager

logger = logging.getLogger(__name__)

class UserInputHelper:
    def __init__(self):
        self.user_input_queue = asyncio.Queue()

    def get_user_input_func(self) -> Callable[[str, Optional[CancellationToken]], Awaitable[str]]:
        async def user_input(prompt: str, cancellation_token: Optional[CancellationToken]) -> str:
            return await self.user_input_queue.get()

        return user_input

    async def recv_user_input(self, text: str):
        await self.user_input_queue.put(text)

class AgentManager:
    def __init__(self):
        # 获取环境变量
        self.api_key = os.getenv("OPENAI_API_KEY")
        self.ticktick_client_id = os.getenv("TICKTICK_CLIENT_ID")
        self.ticktick_client_secret = os.getenv("TICKTICK_CLIENT_SECRET")
        self.openroute_api_key = os.getenv("OPENROUTE_API_KEY")
        
        if not all([self.api_key, self.ticktick_client_id, self.ticktick_client_secret]):
            raise ValueError("Missing required environment variables")
        
        if not isinstance(self.ticktick_client_id, str) or not isinstance(self.ticktick_client_secret, str):
            raise TypeError("TickTick client_id and client_secret must be strings")
    
    def init_agents(self) -> Tuple[AssistantAgent, UserProxyAgent, OpenAIChatCompletionClient, UserInputHelper]:
        """初始化代理和模型客户端"""
        # 初始化任务管理器
        task_manager = TaskManager(self.ticktick_client_id, self.ticktick_client_secret)

        # 创建模型客户端
        model_client = OpenAIChatCompletionClient(
            model="anthropic/claude-3.7-sonnet",
            api_key=self.openroute_api_key,
            base_url="https://openrouter.ai/api/v1",
            model_info={
                "vision": False,
                "function_calling": True,
                "json_output": True,
                "family": "unknown",
            },
            llm_config={
                "cache_seed": 42,  # 启用缓存，种子为42
                "cache_path_root": ".cache/llm_cache"  # 指定缓存目录
            }
        )

        # 创建任务管理助手
        assistant = AssistantAgent(
            name="task_assistant",
            system_message="""
            You are an expert task management assistant for TickTick's Inbox. You help users manage their tasks efficiently using the following capabilities:

            Available Functions:

            1. create_task(title, content='', due_date=None, start_date=None, is_all_day=True, priority=0)
               - Creates a new task in Inbox with the following parameters:
                 * title: Task title (required)
                 * content: Task description
                 * due_date: Due date in 'YYYY-MM-DD' format
                 * start_date: Start date in 'YYYY-MM-DD' format
                 * is_all_day: Whether it's an all-day task
                 * priority: Task priority (0=none, 1=low, 3=medium, 5=high)

            2. list_tasks()

            3. complete_task(task_id)
               - Marks a task as completed
               - Requires task_id from list_tasks

            4. delete_task(task_id)
               - Removes a task from Inbox
               - Requires task_id from list_tasks

            5. get_tasks_by_date(start_date, end_date=None)
               - Gets tasks within a date range:
                 * start_date: Start date 'YYYY-MM-DD'
                 * end_date: Optional end date 'YYYY-MM-DD'

            6. get_completed_tasks()
               - Retrieves all completed tasks from Inbox

            Always follow these steps:
            1. UNDERSTAND: Analyze the user's request carefully
            2. VALIDATE: Ensure you have all required information
            3. EXECUTE: Perform the requested operation
            4. VERIFY: Check the result and provide clear feedback

            Important Notes:
            - All dates must be in 'YYYY-MM-DD' format
            - Priority levels: 0=none, 1=low, 3=medium, 5=high
            - All operations are performed in the Inbox
            - Task IDs are required for complete_task and delete_task

            Say 'goodbye' to end the conversation.
            """,
            tools=[
                task_manager.create_task,
                task_manager.list_tasks,
                task_manager.complete_task,
                task_manager.delete_task,
                task_manager.get_tasks_by_date,
                task_manager.get_completed_tasks
            ],
            model_client=model_client,
            description='''An expert task management assistant for TickTick's Inbox. You help users manage their tasks efficiently using the following capabilities:

            Available Functions:

            1. create_task(title, content='', due_date=None, start_date=None, is_all_day=True, priority=0)
               - Creates a new task in Inbox with the following parameters:
                 * title: Task title (required)
                 * content: Task description
                 * due_date: Due date in 'YYYY-MM-DD' format
                 * start_date: Start date in 'YYYY-MM-DD' format
                 * is_all_day: Whether it's an all-day task
                 * priority: Task priority (0=none, 1=low, 3=medium, 5=high)

            2. list_tasks()

            3. complete_task(task_id)
               - Marks a task as completed
               - Requires task_id from list_tasks

            4. delete_task(task_id)
               - Removes a task from Inbox
               - Requires task_id from list_tasks

            5. get_tasks_by_date(start_date, end_date=None)
               - Gets tasks within a date range:
                 * start_date: Start date 'YYYY-MM-DD'
                 * end_date: Optional end date 'YYYY-MM-DD'

            6. get_completed_tasks()
               - Retrieves all completed tasks from Inbox
            '''
        )

        user_input_helper = UserInputHelper()

        # 创建用户代理
        user_proxy = UserProxyAgent(
            name="user",
            input_func=user_input_helper.get_user_input_func(),
        )

        return assistant, user_proxy, model_client, user_input_helper
    
    def create_team(self, assistant, user_proxy, model_client):
        """创建团队"""
        return MagenticOneGroupChat(
            participants=[user_proxy, assistant],
            model_client=model_client,
            max_turns=20,
            max_stalls=3,
            final_answer_prompt="最后必须给出答案总结"
        )
    
    def task_prompt(self, user_request: str, history_digest: str) -> str:
        """根据用户请求生成任务提示"""
        task_description = """{user_request}"""

        if history_digest:
            task_description += """
    ## Background Information
    User's previous requests have been summarized as follows:
    {history_digest}
    """
        return task_description.format(user_request=user_request, history_digest=history_digest) 