from .client import TickTickClient
from dotenv import load_dotenv
import os
import time
import requests

def main():
    # 加载环境变量
    load_dotenv()
    
    client_id = os.getenv('TICKTICK_CLIENT_ID')
    client_secret = os.getenv('TICKTICK_CLIENT_SECRET')
    redirect_uri = os.getenv('TICKTICK_REDIRECT_URI', 'http://localhost:8080/callback')
    
    if not client_id or not client_secret:
        print('错误: 请在 .env 文件中设置 TICKTICK_CLIENT_ID 和 TICKTICK_CLIENT_SECRET')
        return
    
    # 初始化客户端
    client = TickTickClient(
        client_id=client_id,
        client_secret=client_secret,
        redirect_uri=redirect_uri
    )
    
    # 运行认证流程
    max_retries = 3
    retry_delay = 5
    
    for attempt in range(max_retries):
        try:
            client.authenticate()
            print('认证成功！')
            
            # 验证认证是否有效
            try:
                client.load_projects()
                return  # 如果成功加载项目，则认证成功
            except requests.exceptions.HTTPError as e:
                if e.response.status_code == 401:
                    print('认证失败: 无效的访问令牌')
                else:
                    print(f'验证认证失败: {e}')
            
        except Exception as e:
            if attempt < max_retries - 1:
                print(f'认证失败 ({attempt + 1}/{max_retries}): {e}')
                print(f'将在 {retry_delay} 秒后重试...')
                time.sleep(retry_delay)
            else:
                print(f'认证失败: {e}')
                print('请确保:')
                print('1. 客户端 ID 和密钥正确')
                print('2. 回调 URL 已经在 TickTick 开发者中心配置')
                print('3. 网络连接正常')

if __name__ == "__main__":
    main()
