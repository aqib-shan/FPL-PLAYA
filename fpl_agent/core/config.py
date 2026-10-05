"""
Configuration management for FPL Agent
"""

import os
import yaml
from typing import Dict, Any, Optional
from pathlib import Path
from dotenv import load_dotenv


class Config:
    """Configuration manager for FPL Agent"""
    
    def __init__(self, config_path: Optional[str] = None):
        """Initialize configuration from YAML file and environment variables"""
        load_dotenv()  # Load environment variables from .env file
        
        if config_path is None:
            config_path = Path(__file__).parent.parent / "config.yaml"
        
        self.config_path = Path(config_path)
        self._config = self._load_config()
        
    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from YAML file"""
        if not self.config_path.exists():
            raise FileNotFoundError(f"Config file not found: {self.config_path}")
        
        with open(self.config_path, 'r') as f:
            config = yaml.safe_load(f)
        
        # Override with environment variables
        config = self._override_with_env(config)
        
        return config
    
    def _override_with_env(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Override config values with environment variables"""
        env_mappings = {
            'GEMINI_API_KEY': ('llm', 'api_key'),
            'OPENROUTER_API_KEY': ('llm', 'openrouter_api_key'),
        }
        
        for env_var, config_path in env_mappings.items():
            env_value = os.getenv(env_var)
            if env_value:
                # Navigate to nested config
                current = config
                for key in config_path[:-1]:
                    if key not in current:
                        current[key] = {}
                    current = current[key]
                current[config_path[-1]] = env_value
        
        return config
    
    def get_team_config(self) -> Dict[str, Any]:
        """Get team configuration"""
        return self._config.get('team', {})
    
    def get_llm_model_config(self, model_name: str) -> Dict[str, Any]:
        """Get LLM configuration for a specific model by name"""
        llm_config = self._config.get('llm', {})
        
        # Look for the model in the llm config
        if model_name in llm_config:
            return llm_config[model_name]
        
        # If not found, raise an error with available options
        available_models = list(llm_config.keys())
        raise ValueError(
            f"Model '{model_name}' not found in config. "
            f"Available models: {available_models}"
        )
    
    def get_embeddings_config(self) -> Dict[str, Any]:
        """Get embeddings configuration"""
        return self._config.get('embeddings', {})
    
    def get_position_limits(self) -> Dict[str, int]:
        """Get squad position limits"""
        team_config = self.get_team_config()
        return team_config.get('position_limits', {
            'GK': 2, 'DEF': 5, 'MID': 5, 'FWD': 3
        })
    
    def get_formation_constraints(self) -> Dict[str, list]:
        """Get starting 11 formation constraints"""
        team_config = self.get_team_config()
        return team_config.get('formation_constraints', {}).get('starting_11', {
            'DEF': [3, 5], 'MID': [3, 5], 'FWD': [1, 3]
        })
    
    def get_display_config(self) -> Dict[str, Any]:
        """Get display configuration"""
        return self._config.get('display', {}) 