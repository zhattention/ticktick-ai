import os
import pytest
import asyncio
from dotenv import load_dotenv
from autogen_ext.models.openai import OpenAIChatCompletionClient
from autogen_agentchat.agents import AssistantAgent, UserProxyAgent
from session import Session, ConsoleHandler, SessionResult
from autogen_agentchat.teams import MagenticOneGroupChat, RoundRobinGroupChat
from autogen_agentchat.base import TaskResult
from autogen_agentchat.ui import Console
# Load environment variables
load_dotenv()

@pytest.fixture
def model_client():
    api_key = os.getenv("CEREBRAS_API_KEY")
    if not api_key:
        pytest.skip("CEREBRAS_API_KEY not found in environment variables")
    
    return OpenAIChatCompletionClient(
        model="llama-3.3-70b",
        api_key=api_key,
        base_url="https://api.cerebras.ai/v1",
        model_info={
            "vision": False,
            "function_calling": True,
            "json_output": True,
            "family": "unknown",
        },
        llm_config={
            "cache_seed": 42,  # Enable caching with seed 42
            "cache_path_root": ".cache/llm_cache"  # Specify cache directory
        }
    )

@pytest.fixture
def assistant(model_client):
    """"""
    return AssistantAgent(
        name="test_assistant",
        system_message="""You are a helpful AI assistant. 
        Keep your responses brief and to the point.
        Say 'goodbye' to end the conversation.""",
        model_client=model_client,
    )

@pytest.fixture
def team(assistant, user_proxy, model_client):
    return MagenticOneGroupChat(
        participants=[user_proxy, assistant],
        model_client=model_client,
        max_turns=20,
        max_stalls=3,
        final_answer_prompt="Here is the final answer:"
    )
class QueueUserInput:
    def __init__(self):
        self.queue = asyncio.Queue()

    async def input(self, text: str) -> None:
        await self.queue.put(text)

    def get_user_input_func(self):
        """返回符合 input_func 签名的函数"""
        async def user_input_func(prompt: str, cancellation_token) -> str:
            return await self.queue.get()
        return user_input_func

@pytest.fixture
def user_input_queue() -> QueueUserInput:
    return QueueUserInput()

@pytest.fixture
def user_proxy(user_input_queue):
    """创建用户代理"""
    return UserProxyAgent(
        name="test_user",
        input_func=user_input_queue.get_user_input_func(),
    )

@pytest.fixture
def console_handler():
    """创建控制台消息处理器"""
    return ConsoleHandler()

class TestSession:
    @pytest.mark.asyncio
    async def test_start_session(self, team, model_client, console_handler, user_input_queue):
        """测试开始新会话"""
        print("\n=== Testing Start Session ===\n")
        session = Session(team, model_client)
        
        # 启动会话
        session.start("Help me solve a math problem", console_handler)
        
        # 验证会话状态
        assert session.is_active == True
        assert session.message_handler == console_handler
        assert session.stream is not None

        # First run should request user input
        result = await session.run_until_stop()
        assert result == SessionResult.USER_INPUT_REQUESTED
        assert result.last_message is not None  # Should have some message content

        # Provide user input
        await user_input_queue.input("which is bigger, 9.9 or 9.11?")

        # Second run should finish the conversation
        result = await session.run_until_stop()
        assert result == SessionResult.FINISHED
        assert result.last_message is not None  # Should have the final response
        print(result.last_message)

    @pytest.mark.asyncio
    async def test_multiple_sessions(self, team, model_client, console_handler, user_input_queue):
        """测试多个会话串联执行，历史记录传递"""
        print("\n=== Testing Multiple Sessions ===\n")
        
        # First session
        session1 = Session(team, model_client)
        initial_prompt = "Help me solve a math problem"
        session1.start(initial_prompt, console_handler)
        
        # First session: Get initial response
        result = await session1.run_until_stop()
        assert result == SessionResult.USER_INPUT_REQUESTED
        first_response = result.last_message
        
        # First session: Provide user input
        user_question = "which is bigger, 9.9 or 9.11?"
        await user_input_queue.input(user_question)
        
        # First session: Get final response
        result = await session1.run_until_stop()
        # assert result == SessionResult.FINISHED

        # 获取第一轮对话的摘要
        first_round_digest = await session1.digest()
        print("\nFirst round digest:")
        print(first_round_digest)

        # 第二轮对话，使用第一轮的摘要作为背景
        print("\n=== Starting Second Session with Previous Context ===")
        session2 = Session(team, model_client)
        
        # 构建带有背景信息的提示词
        background = f"Previous conversation summary:\n{first_round_digest}"
        prompt = f"{background}\n\nBased on this context, can you explain why 9.11 is bigger than 9.9 in mathematical terms?"
        
        print("\nPrompt for second session:")
        print(prompt)
        
        session2.start(prompt, console_handler)
        result = await session2.run_until_stop()

        print(f"session2 result: {result.last_message}")
        
        # 打印第二轮的摘要
        second_round_digest = await session2.digest()
        print("\nSecond round digest:")
        print(second_round_digest)

    # @pytest.mark.asyncio
    # async def test_handle_input_new_session(self, team,  model_client, console_handler):
    #     """测试处理新会话的输入"""
    #     print("\n=== Testing Handle Input (New Session) ===\n")
    #     session = Session(team, model_client)
        
    #     # 启动会话
    #     session.start("Help me solve a math problem", console_handler)

    #     user_req_prompt = await session.run_until_user()

    #     print(user_req_prompt)

    #     await session.run_until_user()

        # await session.input("which is bigger, 9.9 or 9.11?")

        # await session.run_until_user()

    # @pytest.mark.asyncio
    # async def test_handle_input_existing_session(self, assistant, user_proxy, model_client, console_handler):
    #     """测试向现有会话注入输入"""
    #     print("\n=== Testing Handle Input (Existing Session) ===\n")
    #     session = Session(assistant, model_client)
        
    #     # 首先启动一个会话
    #     print("[User] Let's have a conversation")
    #     session.start("Let's have a conversation", console_handler)
        
    #     # 等待一下，确保会话开始但不要太久
    #     await asyncio.sleep(1)
    #     assert session.is_active == True, "会话应该处于活跃状态"
        
    #     # 向现有会话注入新输入
    #     new_input = "Tell me more"
    #     print(f"[User] {new_input}")
    #     await session.handle_input(new_input, console_handler)  # 添加 console_handler
        
    #     # 验证输入是否被加入队列
    #     queue_content = await session.voice_queue.get()
    #     assert queue_content == new_input
        
    #     # 等待响应完成
    #     await asyncio.sleep(5)
        
    #     # 显示所有消息
    #     messages = console_handler.get_messages()
    #     assert len(messages) > 0, "应该有至少一条消息"

    # @pytest.mark.asyncio
    # async def test_multiple_sessions(self, assistant, user_proxy, model_client, console_handler):
    #     """测试多个会话的处理"""
    #     print("\n=== Testing Multiple Sessions ===\n")
    #     session = Session(assistant, model_client)
        
    #     # 第一个会话
    #     print("[User] First message")
    #     await session.start("First message", console_handler)
    #     assert session.is_active == True
    #     await asyncio.sleep(2)
        
    #     # 尝试启动第二个会话（应该被阻止）
    #     print("\n[User] Second message (should be blocked)")
    #     await session.start("Second message", console_handler)
        
    #     # 验证仍然是第一个会话
    #     assert session.is_active == True
        
    #     # 等待响应完成
    #     await asyncio.sleep(5)
        
    #     # 显示所有消息
    #     messages = console_handler.get_messages()
    #     assert len(messages) > 0, "应该有至少一条消息"
