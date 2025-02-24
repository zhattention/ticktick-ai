import logging
from abc import ABC, abstractmethod
from typing import Tuple, Optional
from session import Session, SessionResult
from server.agent_manager import AgentManager as TeamAgentManager
from server.agent_manager1 import AgentManager as DirectAgentManager

logger = logging.getLogger(__name__)

class AgentStrategy(ABC):
    """代理策略接口，定义了代理交互的通用方法"""
    
    @abstractmethod
    async def initialize(self) -> None:
        """初始化代理策略"""
        pass
    
    @abstractmethod
    async def process_message(self, text: str) -> Tuple[Optional[str], Optional[str]]:
        """
        处理用户消息
        
        Args:
            text (str): 用户消息
            
        Returns:
            Tuple[Optional[str], Optional[str]]: (状态, 消息内容)
        """
        pass
    
    @property
    @abstractmethod
    def history_digest(self) -> str:
        """获取历史摘要"""
        pass


class TeamAgentStrategy(AgentStrategy):
    """团队代理策略，使用MagenticOneGroupChat实现"""
    
    def __init__(self):
        self.agent_manager = TeamAgentManager()
        self.session = None
        self.user_input_helper = None
        self._history_digest = ""
    
    async def initialize(self) -> None:
        """初始化团队代理"""
        assistant, user_proxy, model_client, user_input_helper = self.agent_manager.init_agents()
        team = self.agent_manager.create_team(assistant, user_proxy, model_client)
        self.session = Session(team, model_client)
        self.user_input_helper = user_input_helper
        logger.info("Session initialized with team interaction")
    
    async def process_message(self, text: str) -> Tuple[Optional[str], Optional[str]]:
        """处理用户消息，使用团队交互模式"""
        # 确保会话已初始化
        if not self.session:
            await self.initialize()
        
        # 处理会话
        if not self.session.is_active:
            self.session.start(self.agent_manager.task_prompt(text, self._history_digest))
        else:
            await self.user_input_helper.recv_user_input(text)
        
        # 继续推理
        result: SessionResult = await self.session.run_until_stop()
        
        # 处理结果
        if result == SessionResult.FINISHED:
            # 会话结束，生成摘要
            self._history_digest = await self.session.digest()
            logger.info(f"History digest: {self._history_digest}")
            
            # 创建新会话
            await self.initialize()
            
            return result.status, self._history_digest
        
        # 返回最后的消息
        if result.last_message:
            logger.info(f"Sent result: [{result.status}] {result.last_message}")
            return result.status, result.last_message
        
        return None, None
    
    @property
    def history_digest(self) -> str:
        """获取历史摘要"""
        return self._history_digest


class DirectAgentStrategy(AgentStrategy):
    """直接代理策略，直接与助手交互"""
    
    def __init__(self):
        self.agent_manager = DirectAgentManager()
        self._history_digest = ""
    
    async def initialize(self) -> None:
        """初始化直接代理"""
        self.agent_manager.init_agent()
        logger.info("Session initialized with direct agent interaction")
    
    async def process_message(self, text: str) -> Tuple[Optional[str], Optional[str]]:
        """处理用户消息，使用直接交互模式"""
        # 确保代理已初始化
        if not self.agent_manager.assistant:
            await self.initialize()
        
        # 直接处理消息并获取响应
        response = await self.agent_manager.process_message(text, self._history_digest)
        
        # 检查是否需要生成新的摘要
        if "goodbye" in response.lower() or "再见" in response:
            # 生成对话历史摘要
            self._history_digest = await self.agent_manager.generate_digest()
            logger.info(f"Generated history digest: {self._history_digest}")
            
            # 返回结束状态和响应
            return "finished", response
        
        # 返回正常状态和响应
        logger.info(f"Sent response: {response[:100]}...")
        return "user_input_requested", response
    
    @property
    def history_digest(self) -> str:
        """获取历史摘要"""
        return self._history_digest


def create_agent_strategy(use_direct_agent: bool = False) -> AgentStrategy:
    """
    创建代理策略
    
    Args:
        use_direct_agent (bool): 是否使用直接代理交互模式
        
    Returns:
        AgentStrategy: 代理策略实例
    """
    if use_direct_agent:
        return DirectAgentStrategy()
    else:
        return TeamAgentStrategy() 