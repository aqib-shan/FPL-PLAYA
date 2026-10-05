"""
LLM Engine Factory for creating appropriate engine based on provider
"""

from typing import Union
from .llm_engine import LLMEngine
from .openrouter_engine import OpenRouterEngine
from ..core.config import Config


def create_llm_engine(config: Config, model_name: str) -> Union[LLMEngine, OpenRouterEngine]:
    """
    Factory function to create the appropriate LLM engine based on provider configuration.
    
    Args:
        config: Main FPL configuration
        model_name: Name of the model config to use (e.g., "main", "openrouter_gpt5")
        
    Returns:
        Appropriate LLM engine instance (LLMEngine or OpenRouterEngine)
        
    Raises:
        ValueError: If provider is not supported
    """
    # Get the model config to check provider
    model_config = config.get_llm_model_config(model_name)
    provider = model_config.get('provider', 'openrouter')
    
    if provider == 'gemini':
        return LLMEngine(config, model_name)
    elif provider == 'openrouter':
        return OpenRouterEngine(config, model_name)
    else:
        raise ValueError(f"Unsupported provider '{provider}' for model '{model_name}'. Supported providers: 'gemini', 'openrouter'")
