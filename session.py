import asyncio
import logging
from abc import ABC, abstractmethod
from typing import Optional, Any
from autogen_agentchat.ui._console import Console

class MessageHandler(ABC):
    """Message handler interface for handling session message sending and receiving"""
    
    @abstractmethod
    async def send_message(self, message: str) -> None:
        """Send message"""
        pass

    @abstractmethod
    async def send_error(self, error: str) -> None:
        """Send error message"""
        pass


class WebSocketHandler(MessageHandler):
    """WebSocket message handler implementation"""
    
    def __init__(self, websocket):
        self.websocket = websocket

    async def send_message(self, message: str) -> None:
        await self.websocket.send_text(str(message))

    async def send_error(self, error: str) -> None:
        await self.websocket.send_text(str(error))


class ConsoleHandler(MessageHandler):
    """Console message handler implementation for testing"""
    
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
        Initialize Session class.
        
        Args:
            team: Chat team instance (e.g., MagenticOneGroupChat).
            model_client: Model client for chat.
        """
        self.team = team
        self.model_client = model_client
        self.stream = None  # Current conversation stream
        self.is_active = False  # Whether the session is active
        self.task = None  # Async task for executing the stream
        self.voice_queue = asyncio.Queue()  # Create input queue
        self.message_handler: Optional[MessageHandler] = None

    def start_session(self, text: str, message_handler: MessageHandler):
        """
        Start a new session, create stream and start execution task.
        
        Args:
            text (str): Initial user input.
            message_handler (MessageHandler): Message handler instance.
        """
        if self.is_active:
            logging.warning("Active session exists, cannot create new session.")
            return

        # Set up message handler
        self.message_handler = message_handler

        # Create new stream
        self.stream = self.team.run_stream(task=text)
        self.is_active = True

        # Start async task to execute stream
        self.task = asyncio.create_task(self.run_stream())

    async def run_stream(self):
        """
        Execute stream and send final results upon completion.
        """
        try:
            # Execute stream and get results
            result = await Console(self.stream)
            final_message = result.messages[-1].content if result.messages else "No response generated"
            await self.message_handler.send_message(final_message)
            logging.info(f"Session ended, final result sent: {final_message}")
        except Exception as e:
            error_msg = f"Stream execution error: {str(e)}"
            logging.error(error_msg)
            await self.message_handler.send_error(error_msg)
        finally:
            # Session ended, clean up state
            self.is_active = False
            self.stream = None
            self.task = None
            self.message_handler = None

    async def handle_input(self, text: str, message_handler: Optional[MessageHandler] = None):
        """
        Handle user input.
        
        If no active session exists, create a new one;
        If an active session exists, inject input into current session.
        
        Args:
            text (str): User input text.
            message_handler (Optional[MessageHandler]): Message handler instance, only required when creating a new session.
        """
        if not self.is_active:
            # No active session, create new one
            if message_handler is None:
                raise ValueError("message_handler must be provided when creating a new session")
            self.start_session(text, message_handler)
            logging.info(f"Creating new session with initial input: {text}")
        else:
            # Active session exists, inject input into current stream
            await self.voice_queue.put(text)
            logging.info(f"Injecting input into current session: {text}")
