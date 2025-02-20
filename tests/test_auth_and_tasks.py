import os
from datetime import datetime, timedelta
from ticktick_client import TickTickClient
from dotenv import load_dotenv

def main():
    # 加载环境变量
    load_dotenv()
    
    # 初始化客户端
    client = TickTickClient(
        client_id=os.getenv('TICKTICK_CLIENT_ID'),
        client_secret=os.getenv('TICKTICK_CLIENT_SECRET')
    )
    
    try:
        # 1. 测试认证
        print("\n1. 测试认证")
        client.authenticate(force_new=True)  # 强制获取新的令牌
        print("认证成功！")
        
        # 2. 测试获取所有任务
        print("\n2. 测试获取所有任务")
        start_date = datetime.now().strftime('%Y-%m-%d')
        end_date = (datetime.now() + timedelta(days=7)).strftime('%Y-%m-%d')
        tasks = client.get_tasks(start_date=start_date, end_date=end_date)
        print(f"获取到 {len(tasks)} 个任务:")
        for task in tasks:
            project_name = task.get('project', {}).get('name', 'Unknown')
            print(f"- [{project_name}] {task['title']}")
            
        # 3. 测试获取 Inbox 任务
        print("\n3. 测试获取 Inbox 任务")
        inbox_tasks = client.get_inbox_tasks()
        print(f"获取到 {len(inbox_tasks)} 个 Inbox 任务:")
        for task in inbox_tasks:
            print(f"- {task['title']}")
            
    except Exception as e:
        print(f"测试过程中出现错误: {e}")

if __name__ == "__main__":
    main()
