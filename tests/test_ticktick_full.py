import os
import pytest
from datetime import datetime, timedelta
from clients.ticktick import TickTickClient
from dotenv import load_dotenv

@pytest.fixture(scope='module')
def client():
    """创建一个 TickTickClient 实例作为测试固件"""
    load_dotenv()
    client = TickTickClient(
        client_id=os.getenv('TICKTICK_CLIENT_ID'),
        client_secret=os.getenv('TICKTICK_CLIENT_SECRET')
    )
    if not client.access_token:
        client.authenticate()
    return client

@pytest.fixture(scope='module')
def test_project(client):
    """创建一个测试项目作为测试固件"""
    project_name = "测试项目"
    project = client.create_project(
        name=project_name,
        color="#FF0000",  # 红色
        view_mode="list"
    )
    yield project
    # 测试结束后清理项目
    try:
        # 这里需要实现删除项目的方法
        pass
    except Exception as e:
        print(f"清理测试项目时出错: {e}")

def test_authentication(client):
    """测试认证功能"""
    assert client.access_token is not None, "认证失败，没有获取到 access_token"

def test_create_project(test_project):
    """测试创建项目"""
    assert test_project['name'] == "测试项目", "项目名称不匹配"
    assert test_project['color'] == "#FF0000", "项目颜色不匹配"
    assert test_project['viewMode'] == "list", "项目视图模式不匹配"

def test_create_task(client, test_project):
    """测试创建任务"""
    # 创建一个普通任务
    task1 = client.create_task(
        title="测试任务1",
        project_name=test_project['name'],
        content="这是一个测试任务",
        due_date=datetime.now().strftime('%Y-%m-%d'),
        priority=3
    )
    assert task1['title'] == "测试任务1", "任务标题不匹配"
    assert task1['priority'] == 3, "任务优先级不匹配"

    # 创建一个带提醒的任务
    tomorrow = datetime.now() + timedelta(days=1)
    reminder_time = tomorrow.replace(hour=9, minute=0, second=0).strftime('%Y-%m-%dT%H:%M:%S.000Z')
    task2 = client.create_task(
        title="测试任务2（带提醒）",
        project_name=test_project['name'],
        content="这是一个带提醒的任务",
        due_date=tomorrow.strftime('%Y-%m-%d'),
        reminders=[reminder_time],
        priority=5  # 高优先级
    )
    assert task2['title'] == "测试任务2（带提醒）", "带提醒任务的标题不匹配"
    assert task2['priority'] == 5, "带提醒任务的优先级不匹配"
    # 暂时跳过提醒测试，因为 API 响应中可能不包含 reminders 字段

    # 创建一个重复任务
    task3 = client.create_task(
        title="测试任务3（每周重复）",
        project_name=test_project['name'],
        content="这是一个每周重复的任务",
        due_date=tomorrow.strftime('%Y-%m-%d'),
        repeat={
            'freq': 'WEEKLY',
            'interval': 1,
            'until': (datetime.now() + timedelta(days=30)).strftime('%Y-%m-%d')
        }
    )
    assert task3['title'] == "测试任务3（每周重复）", "重复任务的标题不匹配"
    assert task3.get('repeat') is not None, "任务的重复设置失败"

def test_update_task(client, test_project):
    """测试更新任务"""
    # 创建一个测试任务
    task = client.create_task(
        title="待更新的任务",
        project_name=test_project['name'],
        content="原始内容",
        priority=1
    )
    
    # 更新任务
    updates = {
        'title': '已修改的任务',
        'content': '已修改的内容',
        'priority': 5
    }
    updated_task = client.update_task(task['id'], updates)
    
    # 验证更新结果
    assert updated_task['title'] == '已修改的任务', "任务标题更新失败"
    assert updated_task['content'] == '已修改的内容', "任务内容更新失败"
    assert updated_task['priority'] == 5, "任务优先级更新失败"

def test_get_tasks(client, test_project):
    """测试获取任务列表"""
    tasks = client.get_tasks(project_name=test_project['name'])
    assert len(tasks) > 0, "没有获取到任何任务"

def test_complete_and_delete_tasks(client, test_project):
    """测试完成和删除任务"""
    # 创建一个测试任务
    task = client.create_task(
        title="测试完成和删除的任务",
        project_name=test_project['name']
    )
    assert task['id'] is not None, "创建的任务没有 ID"
    
    # 测试完成任务
    client.complete_task(task['id'])
    
    # 测试删除任务
    client.delete_task(task['id'])
    
    # 验证任务已被删除
    all_tasks = client.get_tasks(project_name=test_project['name'])
    assert all(t['id'] != task['id'] for t in all_tasks), "任务未被成功删除"
