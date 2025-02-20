import asyncio
from autogen_ext.models.openai import OpenAIChatCompletionClient
from autogen_agentchat.agents import AssistantAgent, UserProxyAgent
from autogen_agentchat.teams import MagenticOneGroupChat
from autogen_agentchat.ui import Console
from dotenv import load_dotenv
import os
from agent import TaskManager

load_dotenv()

async def main() -> None:
    # Get the required environment variables
    api_key = os.getenv("OPENAI_API_KEY")
    ticktick_client_id = os.getenv("TICKTICK_CLIENT_ID")
    ticktick_client_secret = os.getenv("TICKTICK_CLIENT_SECRET")
    
    if not api_key:
        raise ValueError("OPENAI_API_KEY environment variable is not set")
    if not ticktick_client_id or not ticktick_client_secret:
        raise ValueError("TICKTICK_CLIENT_ID and TICKTICK_CLIENT_SECRET environment variables must be set")

    # Initialize task manager
    task_manager = TaskManager(ticktick_client_id, ticktick_client_secret)

    # Create the model client
    model_client = OpenAIChatCompletionClient(
        model="gpt-4o",
        api_key=api_key,
    )

    # Create the task management assistant
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

        2. list_tasks(start_date=None, end_date=None, include_completed=False)
           - Lists tasks from Inbox with optional filters:
             * start_date: Start date filter 'YYYY-MM-DD'
             * end_date: End date filter 'YYYY-MM-DD'
             * include_completed: Include completed tasks

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
            task_manager.create_task,  # 创建任务（支持设置标题、内容、日期、优先级等）
            task_manager.list_tasks,    # 列出任务（支持日期范围过滤和显示已完成任务）
            task_manager.complete_task, # 完成任务
            task_manager.delete_task,   # 删除任务
            task_manager.get_tasks_by_date,  # 获取指定日期范围的任务
            task_manager.get_completed_tasks # 获取所有已完成的任务
        ],
        model_client=model_client,
    )

    # Create the user proxy agent
    user_proxy = UserProxyAgent(
        name="user",
        input_func=input,
    )

    # Define task description with available tools
    task_description = """
Available TickTick Task Management Tools:

1. create_task
   - Purpose: Create a new task in Inbox
   - Required Parameters:
     * title: Task title
   - Optional Parameters:
     * content: Task description
     * due_date: Due date (YYYY-MM-DD)
     * start_date: Start date (YYYY-MM-DD)
     * is_all_day: Whether it's an all-day task (default: True)
     * priority: Task priority (0=none, 1=low, 3=medium, 5=high)
   - Returns: Created task information

2. list_tasks
   - Purpose: List tasks from Inbox with filtering options
   - Optional Parameters:
     * start_date: Filter tasks from this date (YYYY-MM-DD)
     * end_date: Filter tasks until this date (YYYY-MM-DD)
     * include_completed: Include completed tasks (default: False)
   - Returns: List of filtered tasks

3. complete_task
   - Purpose: Mark a task as completed
   - Required Parameters:
     * task_id: ID of the task to complete
   - Returns: None

4. delete_task
   - Purpose: Delete a task from Inbox
   - Required Parameters:
     * task_id: ID of the task to delete
   - Returns: None

5. get_tasks_by_date
   - Purpose: Get tasks within a date range
   - Required Parameters:
     * start_date: Start date (YYYY-MM-DD)
   - Optional Parameters:
     * end_date: End date (YYYY-MM-DD)
   - Returns: List of tasks within the date range

6. get_completed_tasks
   - Purpose: Get all completed tasks
   - Returns: List of completed tasks

Important Notes:
- All operations are performed in the Inbox
- Dates must be in YYYY-MM-DD format
- Task IDs are required for completing and deleting tasks
- Priority levels: 0=none, 1=low, 3=medium, 5=high

User Request: 帮我搜索出所有重复执行的任务
"""

    # Create and run the team
    team = MagenticOneGroupChat(
        participants=[user_proxy, assistant],
        model_client=model_client,
        max_turns=20,
        max_stalls=3,
        final_answer_prompt="Based on our analysis of TickTick tasks, here is a summary of duplicate tasks found and recommendations for handling them:"
    )
    await Console(team.run_stream(task=task_description))

if __name__ == "__main__":
    asyncio.run(main())
