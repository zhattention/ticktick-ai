import asyncio
import logging
from typing import Optional, Any
from enum import Enum
from autogen_core import CancellationToken

from pydantic import InstanceOf
from autogen_agentchat.messages import TextMessage
from autogen_agentchat.ui._console import Console
from autogen_agentchat.teams._group_chat._base_group_chat import BaseGroupChat
from autogen_ext.models.openai import OpenAIChatCompletionClient
from autogen_agentchat.base import Response, TaskResult
from autogen_agentchat.messages import (
    AgentEvent,
    ChatMessage,
    ModelClientStreamingChunkEvent,
    MultiModalMessage,
    UserInputRequestedEvent,
)

class SessionResult(Enum):
    USER_INPUT_REQUESTED = "user_input_requested"
    FINISHED = "finished"

    def __init__(self, status: str):
        self.status = status
        self.last_message: Optional[str] = None

class Session:
    def __init__(self, team: BaseGroupChat, model_client:OpenAIChatCompletionClient):
        """
        Initialize Session class.
        
        Args:
            team: Chat team instance (e.g., MagenticOneGroupChat).
            model_client: Model client for chat.
        """
        self._team = team
        self._model_client = model_client
        self._stream = None  # Current conversation stream
        self._task = None  # Async task for executing the stream
        self._input_queue = asyncio.Queue()  # Create input queue
        self._text_history = []  # List to store (content, source) tuples
        self._is_finished = False  # Add finished state flag

    @property
    def is_active(self) -> bool:
        """Check if the session is currently active."""
        return self._stream is not None and not self._is_finished

    def start(self, text: str):
        """
        Start a new session, create stream and start execution task.
        
        Args:
            text (str): Initial user input.
        """
        if self.is_active:
            logging.warning("Active session exists, cannot create new session.")
            return

        # Create new stream
        self._stream = self._team.run_stream(task=text)
        self._is_finished = False  # Reset finished state when starting new session

    def get_history(self) -> list[str]:
        """Get the conversation history.

        Returns:
            list[str]: List of messages in the conversation history.
        """
        return self._text_history.copy()

    async def run_until_stop(self) -> SessionResult:
        result = SessionResult.USER_INPUT_REQUESTED

        async for message in self._stream:
            if isinstance(message, TextMessage):
                self._text_history.append((message.content, message.source))

            elif isinstance(message, UserInputRequestedEvent):
                result = SessionResult.USER_INPUT_REQUESTED
                break

            elif isinstance(message, TaskResult):
                result = SessionResult.FINISHED
                self._is_finished = True
                break
        
        if self._text_history:
            result.last_message = self._text_history[-1][0]  # Get content from the tuple

        return result

    async def digest(self) -> list[str]:
        """
        使用专门的总结agent生成对话历史的摘要。

        返回:
            list[str]: 包含关键点的摘要列表。
        """
        # 检查历史记录是否为空
        if not self._text_history:
            return ["没有可用的对话历史。"]

        from autogen_agentchat.agents import AssistantAgent

        # 创建总结专用的agent
        summarizer = AssistantAgent(
            name="Summarizer",
            system_message="你是一个专门负责总结对话的助手。你的任务是提取对话中的关键信息，并以列表形式返回重要的要点。",
            model_client=self._model_client
        )

        # 将历史记录格式化为带编号的文本
        history_text = "\n".join([f"{i+1}. [{msg[1]}] {msg[0]}" for i, msg in enumerate(self._text_history)])
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
