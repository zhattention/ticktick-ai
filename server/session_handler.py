import logging
from session import Session, SessionResult
from server.agent_manager import AgentManager, UserInputHelper
from server.audio_processor import AudioProcessor

logger = logging.getLogger(__name__)

class SessionHandler:
    def __init__(self):
        self.agent_manager = AgentManager()
        self.audio_processor = AudioProcessor()
        self.session = None
        self.user_input_helper = None
        self.history_digest = ""
    
    async def initialize(self):
        """初始化会话，创建代理和团队"""
        assistant, user_proxy, model_client, user_input_helper = self.agent_manager.init_agents()
        team = self.agent_manager.create_team(assistant, user_proxy, model_client)
        self.session = Session(team, model_client)
        self.user_input_helper = user_input_helper
        logger.info("Created new session")
    
    async def handle_message(self, data: str):
        """
        处理来自客户端的消息
        
        Args:
            data (str): 客户端发送的数据
            
        Returns:
            tuple: (status, message) 状态和消息内容
        """
        try:
            # 确保会话已初始化
            if not self.session:
                await self.initialize()
            
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
            if not self.session.is_active:
                self.session.start(self.agent_manager.task_prompt(text, self.history_digest))
            else:
                await self.user_input_helper.recv_user_input(text)
            
            # 继续推理
            result: SessionResult = await self.session.run_until_stop()
            
            # 处理结果
            if result == SessionResult.FINISHED:
                # 会话结束，生成摘要
                self.history_digest = await self.session.digest()
                logger.info(f"History digest: {self.history_digest}")
                
                # 创建新会话
                await self.initialize()
                
                return result.status, self.history_digest
            
            # 返回最后的消息
            if result.last_message:
                logger.info(f"Sent result: [{result.status}] {result.last_message}")
                return result.status, result.last_message
            
            return None, None
                
        except Exception as e:
            error_msg = f"Error processing request: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return "error", error_msg 