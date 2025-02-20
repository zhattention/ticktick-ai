import requests
from urllib.parse import urlencode
import http.server
import socketserver
import webbrowser
from urllib.parse import parse_qs, urlparse
import threading
import json
import os
from datetime import datetime, timedelta

class OAuthCallbackHandler(http.server.SimpleHTTPRequestHandler):
    auth_code = None
    
    def do_GET(self):
        """处理回调请求"""
        query_components = parse_qs(urlparse(self.path).query)
        
        # 获取授权码
        if 'code' in query_components:
            OAuthCallbackHandler.auth_code = query_components['code'][0]
            # 发送成功响应
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            self.wfile.write(b"Authorization successful! You can close this window.")
        else:
            self.send_response(400)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            self.wfile.write(b"Authorization failed! No code received.")

class TickTickClient:
    def __init__(self, client_id, client_secret, redirect_uri='http://localhost:8080/callback'):
        self.client_id = client_id
        self.client_secret = client_secret
        self.redirect_uri = redirect_uri
        self.base_url = 'https://api.ticktick.com/open/v1'
        self.auth_url = 'https://ticktick.com/oauth/authorize'
        self.token_url = 'https://ticktick.com/oauth/token'
        self.access_token = None
        self.token_file = 'ticktick_token.json'
        self.projects = {}  # 缓存项目信息
        self.inbox_id = None  # 存储 Inbox ID
        self.load_token()
        if self.access_token:
            self.load_projects()
        
    def create_task(self, title, project_name=None, due_date=None, content='', start_date=None, 
                  is_all_day=True, time_zone='UTC', priority=0, reminders=None, repeat=None):
        """创建新任务
        
        Args:
            title (str): 任务标题
            project_name (str, optional): 项目名称，如果不指定则使用 Inbox
            due_date (str, optional): 到期日期，格式为 'YYYY-MM-DD' 或 'YYYY-MM-DDTHH:mm:ss.SSSZ'
            content (str, optional): 任务内容
            start_date (str, optional): 开始日期，格式为 'YYYY-MM-DD' 或 'YYYY-MM-DDTHH:mm:ss.SSSZ'
            is_all_day (bool, optional): 是否为全天任务
            time_zone (str, optional): 时区，默认为 UTC
            priority (int, optional): 优先级 0-5
            reminders (list, optional): 提醒时间列表，格式为 ISO 时间字符串
            repeat (dict, optional): 重复规则，包含 freq, interval, until 等字段
            
        Returns:
            dict: 创建的任务信息
        """
        if not self.access_token:
            raise ValueError('Not authenticated. Please authenticate first.')
            
        # 确保项目列表是最新的
        self.load_projects()
        
        # 确定项目 ID
        project_id = self.inbox_id
        if project_name:
            project_id = next(
                (p['id'] for p in self.projects.values() if p['name'].lower() == project_name.lower()),
                None
            )
            if not project_id:
                # 如果项目不存在，创建新项目
                project = self.create_project(project_name)
                project_id = project['id']
        
        if not project_id:
            raise ValueError('No project ID available. Make sure you are authenticated and have access to projects.')
            
        url = f'{self.base_url}/task'
        headers = {
            'Authorization': f'Bearer {self.access_token}',
            'Content-Type': 'application/json'
        }
        
        task_data = {
            'title': title,
            'projectId': project_id,
            'content': content,
            'isAllDay': is_all_day,
            'timeZone': time_zone,
            'priority': priority
        }
        
        # 处理日期
        if due_date:
            # 如果只提供了日期部分，添加时间部分
            if len(due_date) == 10:  # YYYY-MM-DD 格式
                due_date = f"{due_date}T00:00:00.000Z"
            task_data['dueDate'] = due_date
            
        if start_date:
            if len(start_date) == 10:  # YYYY-MM-DD 格式
                start_date = f"{start_date}T00:00:00.000Z"
            task_data['startDate'] = start_date
            
        # 处理提醒
        if reminders:
            task_data['reminders'] = reminders
            
        # 处理重复规则
        if repeat:
            task_data['repeat'] = repeat
            
        response = requests.post(url, headers=headers, json=task_data)
        
        if response.status_code in [200, 201]:
            task_data = response.json()
            # 如果是 Inbox 任务，保存 Inbox ID
            if not project_name and not self.inbox_id:
                self.inbox_id = task_data['projectId']
            return task_data
        elif response.status_code == 401:
            raise Exception('Unauthorized: Invalid access token')
        elif response.status_code == 400:
            raise Exception(f'Bad request: {response.text}')
        else:
            raise Exception(f'Error creating task: {response.status_code} - {response.text}')
    
    def get_tasks(self, project_name=None, start_date=None, end_date=None):
        """获取任务列表
        
        Args:
            project_name (str, optional): 项目名称，如果不指定则获取所有任务
            start_date (str, optional): 开始日期，格式为 'YYYY-MM-DD'
            end_date (str, optional): 结束日期，格式为 'YYYY-MM-DD'
        
        Returns:
            list: 任务列表
        """
        if not self.access_token:
            raise ValueError('Not authenticated. Please authenticate first.')
            
        headers = {'Authorization': f'Bearer {self.access_token}'}
        
        # 确保项目列表是最新的
        self.load_projects()
        
        if project_name:
            # 获取指定项目的任务
            project_id = next(
                (p['id'] for p in self.projects.values() if p['name'].lower() == project_name.lower()),
                None
            )
            if not project_id:
                raise ValueError(f'Project {project_name} not found')
                
            project_data = self.get_project_data(project_id)
            tasks = project_data.get('tasks', [])
            
            # 添加项目信息到任务中
            for task in tasks:
                task['project'] = {
                    'id': project_id,
                    'name': project_name,
                    'isInbox': False
                }
            return tasks
        else:
            # 获取所有项目的任务
            all_tasks = []
            for project in self.projects.values():
                try:
                    project_data = self.get_project_data(project['id'])
                    tasks = project_data.get('tasks', [])
                    # 添加项目信息到任务中
                    for task in tasks:
                        task['project'] = {
                            'id': project['id'],
                            'name': project['name'],
                            'isInbox': project.get('isInbox', False)
                        }
                    all_tasks.extend(tasks)
                except Exception as e:
                    print(f"Warning: Failed to get tasks for project {project['name']}: {e}")
                    continue
            return all_tasks
    
    def update_task(self, task_id, updates):
        """更新任务
        
        Args:
            task_id (str): 任务ID
            updates (dict): 需要更新的字段，支持以下字段：
                - title (str): 任务标题
                - content (str): 任务内容
                - desc (str): 任务描述
                - isAllDay (bool): 是否为全天任务
                - startDate (str): 开始时间，格式："2019-11-13T03:00:00+0000"
                - dueDate (str): 截止时间，格式："2019-11-13T03:00:00+0000"
                - timeZone (str): 时区，例如："America/Los_Angeles"
                - priority (int): 优先级（0：无，1：低，3：中，5：高）
                - reminders (list): 提醒时间列表
                - items (list): 子任务列表
            
        Returns:
            dict: 更新后的任务信息
        """
        if not self.access_token:
            raise ValueError('Not authenticated. Please authenticate first.')
            
        # 先获取现有任务信息
        task = None
        project_id = None
        for project in self.projects.values():
            try:
                task = self.get_task_by_id(project['id'], task_id)
                if task:
                    project_id = project['id']
                    break
            except:
                continue
                
        if not task:
            raise ValueError(f'Task not found: {task_id}')
            
        # 构建更新数据
        update_data = {
            'id': task_id,
            'projectId': project_id
        }
        
        # 保留原有数据
        for key in ['title', 'content', 'desc', 'isAllDay', 'startDate', 'dueDate', 
                    'timeZone', 'priority', 'reminders', 'items', 'sortOrder']:
            if key in task:
                update_data[key] = task[key]
        
        # 应用更新
        update_data.update(updates)
        
        # 发送更新请求
        url = f'{self.base_url}/task/{task_id}'
        headers = {
            'Authorization': f'Bearer {self.access_token}',
            'Content-Type': 'application/json'
        }
        
        response = requests.post(url, headers=headers, json=update_data)
        
        if response.status_code in [200, 201]:
            return response.json()
        elif response.status_code == 401:
            raise Exception('Unauthorized: Invalid access token')
        elif response.status_code == 404:
            raise Exception(f'Task not found: {task_id}')
        else:
            raise Exception(f'Error updating task: {response.status_code} - {response.text}')
    
    def delete_task(self, task_id):
        """删除任务
        
        Args:
            task_id (str): 任务ID
        """
        if not self.access_token:
            raise ValueError('Not authenticated. Please authenticate first.')
            
        # 先获取任务所属的项目
        project_id = None
        for project in self.projects.values():
            try:
                task = self.get_task_by_id(project['id'], task_id)
                if task:
                    project_id = project['id']
                    break
            except:
                continue
                
        if not project_id:
            raise ValueError(f'Task not found: {task_id}')
            
        url = f'{self.base_url}/project/{project_id}/task/{task_id}'
        headers = {'Authorization': f'Bearer {self.access_token}'}
        
        response = requests.delete(url, headers=headers)
        
        if response.status_code not in [200, 201, 204]:
            if response.status_code == 401:
                raise Exception('Unauthorized: Invalid access token')
            elif response.status_code == 404:
                raise Exception(f'Task not found: {task_id}')
            else:
                raise Exception(f'Error deleting task: {response.status_code} - {response.text}')
                
    def complete_task(self, task_id):
        """完成任务
        
        Args:
            task_id (str): 任务ID
        """
        if not self.access_token:
            raise ValueError('Not authenticated. Please authenticate first.')
            
        # 先获取任务所属的项目
        project_id = None
        for project in self.projects.values():
            try:
                task = self.get_task_by_id(project['id'], task_id)
                if task:
                    project_id = project['id']
                    break
            except:
                continue
                
        if not project_id:
            raise ValueError(f'Task not found: {task_id}')
            
        url = f'{self.base_url}/project/{project_id}/task/{task_id}/complete'
        headers = {'Authorization': f'Bearer {self.access_token}'}
        
        response = requests.post(url, headers=headers)
        
        if response.status_code not in [200, 201]:
            if response.status_code == 401:
                raise Exception('Unauthorized: Invalid access token')
            elif response.status_code == 404:
                raise Exception(f'Task not found: {task_id}')
            else:
                raise Exception(f'Error completing task: {response.status_code} - {response.text}')
        
    def load_projects(self):
        """加载所有项目信息"""
        if not self.access_token:
            return
            
        url = f'{self.base_url}/project'
        headers = {'Authorization': f'Bearer {self.access_token}'}
        
        try:
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            projects = response.json()
            
            # 将项目信息存储在字典中
            self.projects = {p['id']: p for p in projects}
            
            # 设置 Inbox ID
            inbox = next((p for p in projects if p.get('kind') == 'INBOX'), None)
            if inbox:
                self.inbox_id = inbox['id']
        except Exception as e:
            print(f'Error loading projects: {e}')
            
    def create_project(self, name, color=None, view_mode='list', kind='TASK'):
        """创建新项目
        
        Args:
            name (str): 项目名称
            color (str, optional): 项目颜色，例如 '#F18181'
            view_mode (str, optional): 视图模式，'list', 'kanban', 或 'timeline'
            kind (str, optional): 项目类型，'TASK' 或 'NOTE'
            
        Returns:
            dict: 创建的项目信息
        """
        if not self.access_token:
            raise ValueError('Not authenticated. Please authenticate first.')
            
        url = f'{self.base_url}/project'
        headers = {
            'Authorization': f'Bearer {self.access_token}',
            'Content-Type': 'application/json'
        }
        
        project_data = {
            'name': name,
            'viewMode': view_mode,
            'kind': kind.upper()
        }
        if color:
            project_data['color'] = color
        
        response = requests.post(url, headers=headers, json=project_data)
        response.raise_for_status()
        
        # 更新项目缓存
        project = response.json()
        self.projects[project['id']] = project
        return project
        
    def save_inbox_id(self):
        """保存 Inbox ID 到文件"""
        if self.inbox_id:
            with open(self.inbox_id_file, 'w') as f:
                f.write(self.inbox_id)
                
    def save_token(self, token_data):
        """保存访问令牌到文件
        
        Args:
            token_data (dict): 包含 access_token 和 expires_in 的字典
        """
        token_info = {
            'access_token': token_data['access_token'],
            'expires_at': (datetime.now() + timedelta(seconds=token_data['expires_in'])).isoformat(),
            'token_type': token_data['token_type'],
            'scope': token_data['scope']
        }
        
        with open(self.token_file, 'w') as f:
            json.dump(token_info, f, indent=2)
        
        self.access_token = token_data['access_token']
        
    def load_token(self):
        """从文件加载访问令牌"""
        if not os.path.exists(self.token_file):
            return False
            
        try:
            with open(self.token_file, 'r') as f:
                token_info = json.load(f)
                
            # 检查令牌是否过期
            expires_at = datetime.fromisoformat(token_info['expires_at'])
            if datetime.now() < expires_at:
                self.access_token = token_info['access_token']
                return True
            else:
                os.remove(self.token_file)  # 删除过期的令牌文件
                return False
        except Exception as e:
            print(f"加载令牌时出错: {e}")
            return False
            
    def authenticate(self, port=8080, force_new=False):
        """完整的认证流程
        
        Args:
            port (int): 本地服务器端口号
            force_new (bool): 是否强制获取新的令牌，即使现有令牌仍然有效
        """
        # 如果不是强制刷新，且已有有效的访问令牌，则直接返回
        if not force_new and self.access_token:
            return {'access_token': self.access_token}
            
        redirect_uri = f'http://localhost:{port}'
        
        # 重置授权码
        OAuthCallbackHandler.auth_code = None
        
        # 启动本地服务器
        server = socketserver.TCPServer(("", port), OAuthCallbackHandler)
        server.timeout = 60  # 设置超时时间为60秒
        
        # 获取授权URL并打开浏览器
        auth_url = self.get_auth_url(redirect_uri)
        print(f"\n请在浏览器中访问以下URL进行授权:")
        print(auth_url)
        webbrowser.open(auth_url)
        
        print(f"\n等待授权中... 请在浏览器中完成授权")
        
        # 等待回调
        while OAuthCallbackHandler.auth_code is None:
            server.handle_request()
        
        # 关闭服务器
        server.server_close()
        
        # 获取授权码
        auth_code = OAuthCallbackHandler.auth_code
        
        if auth_code:
            print("\n成功获取授权码！正在获取访问令牌...")
            # 使用授权码获取访问令牌
            token_data = self.get_access_token(auth_code, redirect_uri)
            # 保存令牌
            self.save_token(token_data)
            return token_data
        else:
            raise Exception("未能获取授权码")
        
    def get_auth_url(self, redirect_uri, state=None):
        """获取授权URL"""
        params = {
            'client_id': self.client_id,
            'response_type': 'code',
            'redirect_uri': redirect_uri,
            'scope': 'tasks:read tasks:write'
        }
        if state:
            params['state'] = state
        return f"{self.auth_url}?{urlencode(params)}"
    
    def get_access_token(self, code, redirect_uri):
        """使用授权码获取访问令牌"""
        data = {
            'client_id': self.client_id,
            'client_secret': self.client_secret,
            'code': code,
            'grant_type': 'authorization_code',
            'redirect_uri': redirect_uri
        }
        response = requests.post(self.token_url, data=data)
        if response.status_code == 200:
            token_data = response.json()
            return token_data
        else:
            raise Exception(f'Error getting access token: {response.status_code} - {response.text}')

    def get_projects(self):
        """获取项目列表"""
        if not self.access_token:
            raise Exception('Access token not set. Please authenticate first.')
            
        headers = {'Authorization': f'Bearer {self.access_token}'}
        response = requests.get('https://api.ticktick.com/open/v1/project', headers=headers)
        if response.status_code == 200:
            return response.json()
        else:
            raise Exception(f'Error fetching projects: {response.status_code} - {response.text}')

    def get_project_data(self, project_id: str):
        """获取项目详细数据，包括所有任务
        
        Args:
            project_id (str): 项目ID
            
        Returns:
            dict: 包含项目信息、任务列表和列信息的字典
                - project: 项目信息
                - tasks: 未完成的任务列表
                - columns: 项目的列信息（看板视图）
        """
        if not self.access_token:
            raise Exception('Access token not set. Please authenticate first.')
            
        headers = {'Authorization': f'Bearer {self.access_token}'}
        url = f'https://api.ticktick.com/open/v1/project/{project_id}/data'
        
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            return response.json()
        elif response.status_code == 404:
            raise Exception(f'Project not found: project_id={project_id}')
        elif response.status_code == 401:
            raise Exception('Unauthorized: Invalid access token')
        elif response.status_code == 403:
            raise Exception('Forbidden: No permission to access this project')
        else:
            raise Exception(f'Error fetching project data: {response.status_code} - {response.text}')

    def get_task_by_id(self, project_id: str, task_id: str):
        """获取特定项目中的特定任务
        
        Args:
            project_id (str): 项目ID
            task_id (str): 任务ID
            
        Returns:
            dict: 任务详情，包含以下字段：
                - id: 任务ID
                - title: 任务标题
                - content: 任务内容
                - desc: 任务描述
                - isAllDay: 是否全天任务
                - projectId: 所属项目ID
                - timeZone: 时区
                - startDate: 开始时间
                - dueDate: 截止时间
                - priority: 优先级（0：无，1：低，3：中，5：高）
                - status: 状态（0：正常，2：已完成）
                - completedTime: 完成时间
                - items: 子任务列表
        """
        if not self.access_token:
            raise Exception('Access token not set. Please authenticate first.')
            
        headers = {'Authorization': f'Bearer {self.access_token}'}
        url = f'https://api.ticktick.com/open/v1/project/{project_id}/task/{task_id}'
        
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            return response.json()
        elif response.status_code == 404:
            raise Exception(f'Task not found: project_id={project_id}, task_id={task_id}')
        elif response.status_code == 401:
            raise Exception('Unauthorized: Invalid access token')
        elif response.status_code == 403:
            raise Exception('Forbidden: No permission to access this task')
        else:
            raise Exception(f'Error fetching task: {response.status_code} - {response.text}')

    def _get_inbox_id(self):
        """获取用户的 Inbox ID
        
        通过创建一个临时任务到 Inbox 来获取实际的 Inbox ID，
        然后删除这个临时任务。
        
        Returns:
            str: Inbox ID
        """
        if not self.access_token:
            raise Exception('Access token not set. Please authenticate first.')
            
        # 创建一个临时任务到 Inbox
        headers = {
            'Authorization': f'Bearer {self.access_token}',
            'Content-Type': 'application/json'
        }
        
        temp_task = {
            'title': '_temp_task_for_inbox_id',
            'projectId': 'inbox'
        }
        
        # 创建临时任务
        create_response = requests.post(
            'https://api.ticktick.com/open/v1/task',
            headers=headers,
            json=temp_task
        )
        
        if create_response.status_code not in [200, 201]:
            raise Exception(f'Error creating temp task: {create_response.status_code} - {create_response.text}')
            
        # 从响应中获取 Inbox ID
        task_data = create_response.json()
        inbox_id = task_data['projectId']
        
        # 删除临时任务
        delete_response = requests.delete(
            f'https://api.ticktick.com/open/v1/project/{inbox_id}/task/{task_data["id"]}',
            headers=headers
        )
        
        if delete_response.status_code not in [200, 204]:
            print(f'Warning: Failed to delete temp task: {delete_response.status_code} - {delete_response.text}')
            
        return inbox_id
        
    def get_inbox_tasks(self):
        """获取 Inbox 中的任务列表
        
        Returns:
            list: Inbox 中的任务列表
        """
        if not self.access_token:
            raise Exception('Access token not set. Please authenticate first.')
            
        # 如果还没有获取过 Inbox ID，先获取它
        if not self.inbox_id:
            self.inbox_id = self._get_inbox_id()
            
        # 使用 get_project_data 方法获取 Inbox 数据
        inbox_data = self.get_project_data(self.inbox_id)
        return inbox_data['tasks']


if __name__ == '__main__':
    # 初始化客户端
    client = TickTickClient(
        client_id='UJ40V4rQz3AiQ7Hc45',
        client_secret='7X#q$(XzcB8q3^v9Pk88j!4LwBhYH)Bf'
    )
    
    # 自动完成认证流程
    token_data = client.authenticate()
    print("\n成功获取访问令牌:", token_data)
    
    # 获取 Inbox 中的任务
    try:
        inbox_tasks = client.get_inbox_tasks()
        print("\nInbox 中的任务:")
        for task in inbox_tasks:
            print(f"- {task['title']} (ID: {task['id']})")
    except Exception as e:
        print(f"\n获取 Inbox 任务失败: {e}")
        
    # 创建一个新的 Inbox 任务
    try:
        new_task = client.create_task(
            project_id="inbox",  # 使用 "inbox" 作为项目ID
            title="Inbox 测试任务 2",
            content="这是第二个添加到 Inbox 的测试任务",
            isAllDay=True
        )
        print("\n创建的 Inbox 任务:", new_task)
    except Exception as e:
        print(f"\n创建 Inbox 任务失败: {e}")
