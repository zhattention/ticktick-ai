import asyncio
import logging
from abc import ABC, abstractmethod
from typing import Optional, Any
from autogen_agentchat.ui._console import Console

class MessageHandler(ABC):
    """消息处理器接口，用于处理会话消息的发送和接收"""
    
    @abstractmethod
    async def send_message(self, message: str) -> None:
        """发送消息"""
        pass

    @abstractmethod
    async def send_error(self, error: str) -> None:
        """发送错误消息"""
        pass


class WebSocketHandler(MessageHandler):
    """WebSocket消息处理器实现"""
    
    def __init__(self, websocket):
        self.websocket = websocket

    async def send_message(self, message: str) -> None:
        await self.websocket.send_text(str(message))

    async def send_error(self, error: str) -> None:
        await self.websocket.send_text(str(error))


class ConsoleHandler(MessageHandler):
    """控制台消息处理器实现，用于测试"""
    
    def __init__(self, show_prefix: bool = True):
        self.show_prefix = show_prefix
        self.messages = []

    async def send_message(self, message: str) -> None:
        self.messages.append(message)
        prefix = "[Assistant] " if self.show_prefix else ""
        print(f"\n{prefix}{message}\n")

    async def send_error(self, error: str) -> None:
        self.messages.append(f"ERROR: {error}")
        prefix = "[System Error] " if self.show_prefix else ""
        print(f"\n{prefix}{error}\n")

    def get_messages(self) -> list[str]:
        return self.messages.copy()


class Session:
    def __init__(self, team, model_client):
        """
        初始化 Session 类。
        
        参数：
            team: 对话团队实例（例如 MagenticOneGroupChat）。
            model_client: 用于对话的模型客户端。
        """
        self.team = team
        self.model_client = model_client
        self.stream = None  # 当前的对话流
        self.is_active = False  # 会话是否活跃
        self.task = None  # 异步任务，用于执行流
        self.voice_queue = asyncio.Queue()  # 创建输入队列
        self.message_handler: Optional[MessageHandler] = None

    async def start_session(self, text: str, message_handler: MessageHandler):
        """
        开始一个新的会话，创建 stream 并启动执行任务。
        
        参数：
            text (str): 用户的初始输入。
            message_handler (MessageHandler): 消息处理器实例。
        """
        if self.is_active:
            logging.warning("已有活跃会话，无法创建新会话。")
            return

        # 设置消息处理器
        self.message_handler = message_handler

        # 创建新的 stream
        self.stream = self.team.run_stream(task=text)
        self.is_active = True

        # 启动异步任务执行 stream
        self.task = asyncio.create_task(self.run_stream())

    async def run_stream(self):
        """
        执行 stream 并在完成后发送最终结果。
        """
        try:
            # 执行 stream 并获取结果
            result = await Console(self.stream)
            final_message = result.messages[-1].content if result.messages else "No response generated"
            await self.message_handler.send_message(final_message)
            logging.info(f"会话结束，已发送最终结果: {final_message}")
        except Exception as e:
            error_msg = f"流执行出错: {str(e)}"
            logging.error(error_msg)
            await self.message_handler.send_error(error_msg)
        finally:
            # 会话结束，清理状态
            self.is_active = False
            self.stream = None
            self.task = None
            self.message_handler = None

    async def handle_input(self, text: str, message_handler: Optional[MessageHandler] = None):
        """
        处理用户输入。
        
        如果没有活跃会话，则创建新会话；
        如果有活跃会话，则将输入注入当前会话。
        
        参数：
            text (str): 用户输入的文本。
            message_handler (Optional[MessageHandler]): 消息处理器实例，仅在创建新会话时需要。
        """
        if not self.is_active:
            # 没有活跃会话，创建新会话
            if message_handler is None:
                raise ValueError("创建新会话时必须提供message_handler")
            await self.start_session(text, message_handler)
            logging.info(f"创建新会话，初始输入: {text}")
        else:
            # 有活跃会话，注入输入到当前 stream
            await self.voice_queue.put(text)
            logging.info(f"注入输入到当前会话: {text}")
