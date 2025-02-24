import logging
from typing import Dict, Optional
from session import Session, SessionResult
from server.agent_manager import AgentManager as TeamAgentManager
from server.agent_manager1 import AgentManager as DirectAgentManager
from server.audio_processor import AudioProcessor

logger = logging.getLogger(__name__)

class SessionHandler:
    def __init__(self, use_direct_agent=False):
        """
        初始化SessionHandler
        
        Args:
            use_direct_agent (bool): 是否使用直接代理交互模式，默认为False（使用团队模式）
        """
        self.use_direct_agent = use_direct_agent
        self.audio_processor = AudioProcessor()
        
        # 根据模式选择不同的代理管理器
        if use_direct_agent:
            self.direct_agent_manager = DirectAgentManager()
            self.session = None
            self.user_input_helper = None
            self.history_digest = ""
        else:
            self.team_agent_manager = TeamAgentManager()
            self.session = None
            self.user_input_helper = None
            self.history_digest = ""
    
    async def initialize(self):
        """初始化会话，创建代理和团队"""
        if self.use_direct_agent:
            # 直接代理模式
            self.direct_agent_manager.init_agent()
            logger.info("Session initialized with direct agent interaction")
        else:
            # 团队模式
            assistant, user_proxy, model_client, user_input_helper = self.team_agent_manager.init_agents()
            team = self.team_agent_manager.create_team(assistant, user_proxy, model_client)
            self.session = Session(team, model_client)
            self.user_input_helper = user_input_helper
            logger.info("Session initialized with team interaction")
    
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
            if (not self.use_direct_agent and not self.session) or (self.use_direct_agent and not self.direct_agent_manager.assistant):
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

            # 根据模式处理消息
            if self.use_direct_agent:
                # 直接代理模式
                response = await self.direct_agent_manager.process_message(text, self.history_digest)
                
                # 检查是否需要生成新的摘要
                if "goodbye" in response.lower() or "再见" in response:
                    # 生成对话历史摘要
                    self.history_digest = await self.direct_agent_manager.generate_digest()
                    logger.info(f"Generated history digest: {self.history_digest}")
                    
                    # 返回结束状态和响应
                    return "finished", response
                
                # 返回正常状态和响应
                logger.info(f"Sent response: {response[:100]}...")
                return "user_input_requested", response
            else:
                # 团队模式
                # 处理会话
                if not self.session.is_active:
                    self.session.start(self.team_agent_manager.task_prompt(text, self.history_digest))
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