from autogen_agentchat.agents import AssistantAgent
from autogen_agentchat.messages import TextMessage
from autogen_agentchat.ui import Console
from autogen_ext.models.openai import OpenAIChatCompletionClient
from autogen_core import CancellationToken
from clients.ticktick import TickTickClient
import asyncio
from dotenv import load_dotenv
import os

load_dotenv()

async def get_weather(city: str) -> str:
    """Get the weather for a given city."""
    return f"The weather in {city} is 73 degrees and Sunny."

class TaskManager:
    def __init__(self, client_id: str, client_secret: str):
        self.client = TickTickClient(client_id, client_secret)
        self.client.authenticate()
        
    async def create_task(self, title: str, content: str = '', due_date: str = None, start_date: str = None, 
                         is_all_day: bool = True, priority: int = 0) -> dict:
        """创建新任务到 Inbox
        
        Args:
            title (str): 任务标题
            content (str, optional): 任务内容
            due_date (str, optional): 到期日期，格式为 'YYYY-MM-DD'
            start_date (str, optional): 开始日期，格式为 'YYYY-MM-DD'
            is_all_day (bool, optional): 是否为全天任务
            priority (int, optional): 优先级 0-5，0=无，1=低，3=中，5=高
            
        Returns:
            dict: 创建的任务信息
        """
        return self.client.create_task(
            title=title,
            content=content,
            due_date=due_date,
            start_date=start_date,
            is_all_day=is_all_day,
            priority=priority
        )

    async def list_tasks(self) -> str:
        """获取 Inbox 中的任务并转换为 markdown 格式
        
        Returns:
            str: markdown 格式的任务列表
        """
        tasks = self.client.get_inbox_tasks()
        
        if not tasks:
            return "# Inbox Tasks\n\nNo tasks found."
            
        markdown = "# Inbox Tasks\n\n"
        
        for task in tasks:
            # 添加任务标题和内容
            markdown += f"## {task['title']}\n\n"
            
            if task.get('content'):
                markdown += f"{task['content']}\n\n"
                
            # 添加任务详情
            details = []
            if task.get('startDate'):
                details.append(f"- Start: {task['startDate']}")
            if task.get('dueDate'):
                details.append(f"- Due: {task['dueDate']}")
            if task.get('priority'):
                priority_map = {1: "Low", 3: "Medium", 5: "High"}
                details.append(f"- Priority: {priority_map.get(task['priority'], 'Normal')}")
            if task.get('status') is not None:
                status = "Completed" if task['status'] == 2 else "In Progress"
                details.append(f"- Status: {status}")
                
            if details:
                markdown += "\n".join(details) + "\n\n"
            
            # 添加子任务
            if task.get('items'):
                markdown += "### Subtasks\n\n"
                for item in task['items']:
                    status_mark = "✓" if item.get('status') == 2 else "☐"
                    markdown += f"- {status_mark} {item['title']}\n"
                markdown += "\n"
            
            markdown += "---\n\n"
            
        return markdown.strip()

    async def complete_task(self, task_id: str) -> None:
        """完成 Inbox 中的任务
        
        Args:
            task_id (str): 任务ID
        """
        return self.client.complete_task(task_id)

    async def delete_task(self, task_id: str) -> None:
        """删除 Inbox 中的任务
        
        Args:
            task_id (str): 任务ID
        """
        return self.client.delete_task(task_id)
        
    async def get_tasks_by_date(self, start_date: str, end_date: str = None) -> list:
        """获取指定日期范围内的任务
        
        Args:
            start_date (str): 开始日期，格式为 'YYYY-MM-DD'
            end_date (str, optional): 结束日期，格式为 'YYYY-MM-DD'，如果不指定则只获取开始日期的任务
            
        Returns:
            list: 指定日期范围内的任务列表
        """
        if not end_date:
            end_date = start_date
        return self.client.get_inbox_tasks(start_date=start_date, end_date=end_date)
        
    async def get_completed_tasks(self) -> list:
        """获取所有已完成的任务
        
        Returns:
            list: 已完成的任务列表
        """
        tasks = self.client.get_inbox_tasks(include_completed=True)
        return [task for task in tasks if task.get('status') == 2]

async def main() -> None:
    # Get the required environment variables
    api_key = os.getenv("OPENAI_API_KEY")
    ticktick_client_id = os.getenv("TICKTICK_CLIENT_ID")
    ticktick_client_secret = os.getenv("TICKTICK_CLIENT_SECRET")
    
    if not api_key:
        raise ValueError("OPENAI_API_KEY environment variable is not set")
    if not ticktick_client_id or not ticktick_client_secret:
        raise ValueError("TICKTICK_CLIENT_ID and TICKTICK_CLIENT_SECRET environment variables must be set")

    # Create the model client with API key
    model_client = OpenAIChatCompletionClient(
        model="gpt-4",
        api_key=api_key,
    )
    
    # Initialize task manager
    task_manager = TaskManager(ticktick_client_id, ticktick_client_secret)
    
    # Create the assistant agent
    agent = AssistantAgent(
        name="task_agent",
        model_client=model_client,
        tools=[
            task_manager.create_task,
            task_manager.list_tasks,
            task_manager.complete_task,
            task_manager.delete_task
        ],
        system_message="You are a helpful task management assistant. You can help users manage their tasks in TickTick by creating, listing, completing, and deleting tasks.",
    )

    # Create a message and get response
    message = TextMessage(content="List all my tasks", source="user")
    response = await agent.on_messages(
        [message],
        cancellation_token=CancellationToken(),
    )
    
    # Print both the thought process and final response
    print("\nThought process:")
    if response.inner_messages:
        for msg in response.inner_messages:
            print(f"\n{msg}")
    else:
        print("No detailed thought process available")
    
    print("\nFinal response:")
    print(response.chat_message.content)

if __name__ == "__main__":
    asyncio.run(main())