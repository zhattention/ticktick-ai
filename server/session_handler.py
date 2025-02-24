import logging
from typing import Dict
from session import Session, SessionResult
from server.agent_manager import AgentManager, UserInputHelper
from server.audio_processor import AudioProcessor

logger = logging.getLogger(__name__)

class SessionHandler:
    def __init__(self):
        self.agent_manager = AgentManager()
        self.audio_processor = AudioProcessor()
        self.sessions: Dict[int, Session] = {}
        self.history_digests: Dict[int, str] = {}
    
    async def handle_message(self, client_id: int, data: str):
        """
        处理来自客户端的消息
        
        Args:
            client_id (int): 客户端ID
            data (str): 客户端发送的数据
            
        Returns:
            tuple: (status, message) 状态和消息内容
        """
        try:
            # 检查是否是新会话
            if client_id not in self.sessions:
                # 初始化新会话
                assistant, user_proxy, model_client, user_input_helper = self.agent_manager.init_agents()
                team = self.agent_manager.create_team(assistant, user_proxy, model_client)
                self.sessions[client_id] = {
                    "session": Session(team, model_client),
                    "user_input_helper": user_input_helper,
                    "history_digest": ""
                }
                logger.info(f"Created new session for client {client_id}")
            
            session_data = self.sessions[client_id]
            session = session_data["session"]
            user_input_helper = session_data["user_input_helper"]
            history_digest = session_data["history_digest"]
            
            # 处理输入数据
            if data.startswith('data:'):
                # 处理音频数据
                text = self.audio_processor.process_audio(data)
            else:
                # 直接处理文本数据
                text = data
                logger.info(f"Received text data: {text}")

            if text is None or text == "":
                return None, None

            # 处理会话
            if not session.is_active:
                session.start(self.agent_manager.task_prompt(text, history_digest))
            else:
                await user_input_helper.recv_user_input(text)
            
            # 继续推理
            result: SessionResult = await session.run_until_stop()
            
            # 处理结果
            if result == SessionResult.FINISHED:
                # 会话结束，生成摘要
                history_digest = await session.digest()
                logger.info(f"History digest for client {client_id}: {history_digest}")
                
                # 创建新会话
                assistant, user_proxy, model_client, user_input_helper = self.agent_manager.init_agents()
                team = self.agent_manager.create_team(assistant, user_proxy, model_client)
                self.sessions[client_id] = {
                    "session": Session(team, model_client),
                    "user_input_helper": user_input_helper,
                    "history_digest": history_digest
                }
                
                return result.status, history_digest
            
            # 返回最后的消息
            if result.last_message:
                logger.info(f"Sent result to client {client_id}: [{result.status}] {result.last_message}")
                return result.status, result.last_message
            
            return None, None
                
        except Exception as e:
            error_msg = f"Error processing request: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return "error", error_msg 