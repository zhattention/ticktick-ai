import os
import logging
import asyncio
from typing import Awaitable, Callable, Optional, Tuple
from autogen_core import CancellationToken
from autogen_ext.models.openai import OpenAIChatCompletionClient
from autogen_agentchat.agents import AssistantAgent
from autogen_agentchat.messages import TextMessage
from tools.ticktick import TaskManager

logger = logging.getLogger(__name__)

class UserInputHelper:
    def __init__(self):
        self.user_input_queue = asyncio.Queue()
        self.response_queue = asyncio.Queue()

    async def send_user_input(self, text: str):
        """发送用户输入到队列"""
        await self.user_input_queue.put(text)
    
    async def get_response(self):
        """获取助手的响应"""
        return await self.response_queue.get()
    
    async def send_response(self, text: str):
        """发送助手的响应到队列"""
        await self.response_queue.put(text)

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
        
        self.user_input_helper = UserInputHelper()
        self.assistant = None
        self.model_client = None
        self.history = []
    
    def init_agent(self):
        """初始化助手代理"""
        # 初始化任务管理器
        task_manager = TaskManager(self.ticktick_client_id, self.ticktick_client_secret)

        # 创建模型客户端
        self.model_client = OpenAIChatCompletionClient(
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
        self.assistant = AssistantAgent(
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

            At the end of your response, always provide a brief summary of what was accomplished or what the next steps should be.
            """,
            tools=[
                task_manager.create_task,
                task_manager.list_tasks,
                task_manager.complete_task,
                task_manager.delete_task,
                task_manager.get_tasks_by_date,
                task_manager.get_completed_tasks
            ],
            model_client=self.model_client
        )
        
        logger.info("Task assistant initialized")
    
    async def process_message(self, user_message: str, history_digest: str = ""):
        """
        处理用户消息并获取助手的响应
        
        Args:
            user_message (str): 用户的消息
            history_digest (str, optional): 历史对话的摘要
            
        Returns:
            str: 助手的响应
        """
        if not self.assistant:
            self.init_agent()
        
        # 准备消息，包含历史摘要（如果有）
        prompt = user_message
        if history_digest:
            prompt = f"{user_message}\n\n## Background Information\nPrevious conversations summary: {history_digest}"
        
        # 记录用户消息
        self.history.append(("user", prompt))
        
        # 发送消息给助手并获取响应
        response = await self.assistant.on_messages(
            [TextMessage(content=prompt, source="user")],
            CancellationToken()
        )
        
        # 获取助手的回复
        assistant_response = response.chat_message.content
        
        # 记录助手的回复
        self.history.append(("assistant", assistant_response))
        
        return assistant_response
    
    async def generate_digest(self):
        """
        生成对话历史的摘要
        
        Returns:
            str: 对话历史的摘要
        """
        if not self.history:
            return "没有可用的对话历史。"
        
        # 创建摘要专用的agent
        summarizer = AssistantAgent(
            name="Summarizer",
            system_message="你是一个专门负责总结对话的助手。你的任务是提取对话中的关键信息，并以列表形式返回重要的要点。",
            model_client=self.model_client
        )
        
        # 将历史记录格式化为带编号的文本
        history_text = "\n".join([f"{i+1}. [{msg[0]}] {msg[1]}" for i, msg in enumerate(self.history)])
        summary_prompt = (
            "请将以下对话历史总结为简明的关键点列表，"
            "重点保留用户的意图和重要信息：\n\n"
            f"{history_text}\n\n"
        )
        
        # 使用总结agent生成摘要
        response = await summarizer.on_messages(
            [TextMessage(content=summary_prompt, source="user")],
            CancellationToken()
        )
        
        # 返回摘要文本
        return response.chat_message.content
    
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