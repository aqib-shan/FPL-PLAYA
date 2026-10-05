"""
Base class for all LLM strategies.
This provides common functionality shared between different strategy implementations.
"""

import logging
from abc import ABC, abstractmethod

from ..core.config import Config
from .llm_factory import create_llm_engine
from ..data import DataService


logger = logging.getLogger(__name__)


class BaseLLMStrategy(ABC):
    """
    Abstract base class for all LLM strategies.
    
    This class provides common functionality that all LLM strategies share:
    - LLM engine initialization and management
    - Data service access
    - Configuration management
    """
    
    def __init__(self, config: Config, model_name: str):
        """
        Initialize base strategy with common components.
        
        Args:
            config: FPL configuration object
            model_name: Name of the LLM model to use (e.g., "main", "lightweight")
        """
        self.config = config
        self.model_name = model_name
        
        # Initialize LLM engine with specified model using factory
        self.llm_engine = create_llm_engine(config, model_name)
        
        # Initialize data service for all strategies
        self.data_service = DataService(config)
        
        logger.info(f"Initialized {self.__class__.__name__} with model: {model_name}")

    @abstractmethod
    def get_strategy_name(self) -> str:
        """Return the name of this strategy."""
        pass
