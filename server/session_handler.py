import logging
from typing import Optional, Tuple
from server.audio_processor import AudioProcessor
from server.agent_strategy import create_agent_strategy, AgentStrategy

logger = logging.getLogger(__name__)

class SessionHandler:
    def __init__(self, use_direct_agent=False):
        """
        初始化SessionHandler
        
        Args:
            use_direct_agent (bool): 是否使用直接代理交互模式，默认为False（使用团队模式）
        """
        self.audio_processor = AudioProcessor()
        # 使用工厂函数创建适当的策略
        self.strategy: AgentStrategy = create_agent_strategy(use_direct_agent)
    
    async def initialize(self):
        """初始化会话，创建代理和团队"""
        await self.strategy.initialize()
    
    async def handle_message(self, data: str) -> Tuple[Optional[str], Optional[str]]:
        """
        处理来自客户端的消息
        
        Args:
            data (str): 客户端发送的数据
            
        Returns:
            tuple: (status, message) 状态和消息内容
        """
        try:
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

            # 使用策略处理消息
            return await self.strategy.process_message(text)
                
        except Exception as e:
            error_msg = f"Error processing request: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return "error", error_msg
    
    @property
    def history_digest(self) -> str:
        """获取历史摘要"""
        return self.strategy.history_digest 