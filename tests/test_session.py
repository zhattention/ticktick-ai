import os
import pytest
import asyncio
from dotenv import load_dotenv
from autogen_ext.models.openai import OpenAIChatCompletionClient
from autogen_agentchat.agents import AssistantAgent, UserProxyAgent
from session import Session, ConsoleHandler

# Load environment variables
load_dotenv()

@pytest.fixture
def model_client():
    """创建OpenAI模型客户端"""
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        pytest.skip("OPENAI_API_KEY not found in environment variables")
    
    return OpenAIChatCompletionClient(
        model="gpt-4o-mini",
        api_key=api_key,
    )

@pytest.fixture
def assistant(model_client):
    """创建助手代理"""
    return AssistantAgent(
        name="test_assistant",
        system_message="""You are a helpful AI assistant. 
        Keep your responses brief and to the point.
        Say 'goodbye' to end the conversation.""",
        model_client=model_client,
    )

@pytest.fixture
def user_proxy():
    """创建用户代理"""
    async def test_input(prompt: str) -> str:
        return "test response"

    return UserProxyAgent(
        name="test_user",
        input_func=test_input
    )

@pytest.fixture
def console_handler():
    """创建控制台消息处理器"""
    return ConsoleHandler()

class TestSession:
    @pytest.mark.asyncio
    async def test_start_session(self, assistant, user_proxy, model_client, console_handler):
        """测试开始新会话"""
        print("\n=== Testing Start Session ===\n")
        session = Session(assistant, model_client)
        
        # 启动会话
        print("[User] Tell me a joke")
        await session.start_session("Tell me a joke", console_handler)
        
        # 验证会话状态
        assert session.is_active == True
        assert session.message_handler == console_handler
        assert session.stream is not None
        
        # 等待响应完成
        await asyncio.sleep(5)
        
        # 验证会话已正确结束
        assert session.is_active == False
        assert session.stream is None
        assert session.task is None
        assert session.message_handler is None
        
        # 显示所有消息
        messages = console_handler.get_messages()
        assert len(messages) > 0, "应该有至少一条消息"

    @pytest.mark.asyncio
    async def test_handle_input_new_session(self, assistant, user_proxy, model_client, console_handler):
        """测试处理新会话的输入"""
        print("\n=== Testing Handle Input (New Session) ===\n")
        session = Session(assistant, model_client)
        
        # 处理输入
        print("[User] What's the weather like?")
        await session.handle_input("What's the weather like?", console_handler)
        
        # 验证会话状态
        assert session.is_active == True
        assert session.message_handler == console_handler
        
        # 等待响应完成
        await asyncio.sleep(5)
        
        # 验证会话已正确结束
        assert session.is_active == False
        
        # 显示所有消息
        messages = console_handler.get_messages()
        assert len(messages) > 0, "应该有至少一条消息"

    @pytest.mark.asyncio
    async def test_handle_input_existing_session(self, assistant, user_proxy, model_client, console_handler):
        """测试向现有会话注入输入"""
        print("\n=== Testing Handle Input (Existing Session) ===\n")
        session = Session(assistant, model_client)
        
        # 首先启动一个会话
        print("[User] Let's have a conversation")
        await session.start_session("Let's have a conversation", console_handler)
        
        # 等待一下，确保会话开始但不要太久
        await asyncio.sleep(1)
        assert session.is_active == True, "会话应该处于活跃状态"
        
        # 向现有会话注入新输入
        new_input = "Tell me more"
        print(f"[User] {new_input}")
        await session.handle_input(new_input, console_handler)  # 添加 console_handler
        
        # 验证输入是否被加入队列
        queue_content = await session.voice_queue.get()
        assert queue_content == new_input
        
        # 等待响应完成
        await asyncio.sleep(5)
        
        # 显示所有消息
        messages = console_handler.get_messages()
        assert len(messages) > 0, "应该有至少一条消息"

    @pytest.mark.asyncio
    async def test_multiple_sessions(self, assistant, user_proxy, model_client, console_handler):
        """测试多个会话的处理"""
        print("\n=== Testing Multiple Sessions ===\n")
        session = Session(assistant, model_client)
        
        # 第一个会话
        print("[User] First message")
        await session.start_session("First message", console_handler)
        assert session.is_active == True
        await asyncio.sleep(2)
        
        # 尝试启动第二个会话（应该被阻止）
        print("\n[User] Second message (should be blocked)")
        await session.start_session("Second message", console_handler)
        
        # 验证仍然是第一个会话
        assert session.is_active == True
        
        # 等待响应完成
        await asyncio.sleep(5)
        
        # 显示所有消息
        messages = console_handler.get_messages()
        assert len(messages) > 0, "应该有至少一条消息"
