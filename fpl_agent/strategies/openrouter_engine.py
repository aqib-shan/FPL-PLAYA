"""
OpenRouter Engine for API communication
"""

import logging
import requests
from typing import Optional, Dict, Any

from ..core.config import Config

logger = logging.getLogger(__name__)


class OpenRouterEngine:
    """
    OpenRouter engine that works with any OpenRouter model configuration.
    
    This class handles:
    - OpenRouter API initialization and configuration
    - Web search integration when enabled (via :online suffix)
    - Response processing and JSON extraction
    - Error handling for LLM operations
    """
    
    def __init__(self, config: Config, model_name: str):
        """
        Initialize OpenRouter engine.
        
        Args:
            config: Main FPL configuration
            model_name: Name of the model config to use (e.g., "openrouter_gpt5")
        """
        self.config = config
        
        # Get the model config dynamically from the config file
        self.llm_config = config.get_llm_model_config(model_name)
        self.model_name = self.llm_config.get('model')
        
        # Enable web search by appending :online if configured
        if self.llm_config.get('web_search', False):
            self.model_name = f"{self.model_name}:online"
        
        # Get API key from config
        self.api_key = config._config.get('llm', {}).get('openrouter_api_key')
        if not self.api_key:
            raise ValueError("OpenRouter API key not found. Set OPENROUTER_API_KEY environment variable.")
        
        # OpenRouter API endpoint
        self.api_url = "https://openrouter.ai/api/alpha/responses"
        
        logger.info(f"Initialized OpenRouter engine with model: {self.model_name}")
    
    def query(self, prompt: str, response_schema: Optional[dict] = None, max_retries: Optional[int] = None) -> str:
        """
        Query the OpenRouter API with a given prompt and automatic retry on failure.
        
        Args:
            prompt: The prompt to send to the LLM
            response_schema: Optional response schema (not used for OpenRouter)
            max_retries: Maximum number of retry attempts (defaults to config value if None)

        Returns:
            String containing the LLM response
        """
        # Use config value if max_retries not specified
        if max_retries is None:
            max_retries = self.llm_config.get('max_retries', 1)
        
        for attempt in range(max_retries + 1):
            try:
                # Prepare the request payload
                # OpenRouter alpha/responses → xAI expects max_output_tokens (not max_tokens)
                payload = {
                    "model": self.model_name,
                    "input": prompt,
                    "max_output_tokens": self.llm_config.get('max_output_tokens', 8192),
                    "temperature": self.llm_config.get('temperature', 0.3),
                    "top_p": self.llm_config.get('top_p', 0.8),
                }
                # top_k is chat-completions oriented; only send if configured and non-null
                if self.llm_config.get('top_k') is not None:
                    payload["top_k"] = self.llm_config.get('top_k')
                
                # Check payload size (OpenRouter has stricter limits than Gemini API)
                import json
                payload_size = len(json.dumps(payload).encode('utf-8'))
                logger.info(f"OpenRouter request payload size: {payload_size:,} bytes ({payload_size / 1024 / 1024:.2f} MB)")
                
                # OpenRouter typically has a ~1MB limit for the alpha/responses endpoint
                # Warn if approaching limit
                if payload_size > 900000:  # ~900KB
                    logger.warning(f"Large payload detected ({payload_size / 1024 / 1024:.2f} MB). OpenRouter may reject requests over ~1MB.")
                
                # Prepare headers
                headers = {
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                }
                
                # Make the API request
                response = requests.post(
                    self.api_url,
                    json=payload,
                    headers=headers,
                    timeout=600  # 10 minute timeout
                )
                
                # Check for HTTP errors
                response.raise_for_status()
                
                # Parse the response
                response_data = response.json()
                
                # Extract the response text
                text_response = self._extract_text_response(response_data)
                
                # Check if extraction failed
                if text_response.startswith("Error:"):
                    if attempt < max_retries:
                        logger.warning(f"OpenRouter response extraction failed (attempt {attempt + 1}/{max_retries + 1}), retrying...")
                        logger.warning(f"Error: {text_response}")
                        continue  # Try again
                    else:
                        logger.error(f"OpenRouter response extraction failed after {max_retries + 1} attempts")
                        return text_response
                
                # Success!
                if attempt > 0:
                    logger.info(f"OpenRouter query succeeded on retry attempt {attempt + 1}")
                return text_response
                
            except requests.exceptions.HTTPError as e:
                # Prefer provider error body over bare status (e.g. xAI field validation)
                detail = str(e)
                if e.response is not None:
                    try:
                        body = e.response.json()
                        raw = (
                            body.get('error', {}).get('metadata', {}).get('raw')
                            or body.get('error', {}).get('message')
                            or body
                        )
                        detail = f"{e} | {raw}"
                    except Exception:
                        detail = f"{e} | {e.response.text[:500]}"

                # Handle 413 Payload Too Large specifically
                if e.response is not None and e.response.status_code == 413:
                    payload_size = len(json.dumps({"input": prompt}).encode('utf-8'))
                    error_msg = (
                        f"OpenRouter payload too large (413 error). "
                        f"Request size: {payload_size / 1024 / 1024:.2f} MB. "
                        f"OpenRouter's /api/alpha/responses endpoint has stricter size limits than the Gemini API. "
                        f"Consider reducing the number of players in the prompt or using a different model configuration."
                    )
                    logger.error(error_msg)
                    return f"Error: {error_msg}"
                elif attempt < max_retries:
                    logger.warning(f"OpenRouter query failed (attempt {attempt + 1}/{max_retries + 1}), retrying... Error: {detail}")
                    continue
                else:
                    logger.error(f"OpenRouter query failed after {max_retries + 1} attempts: {detail}")
                    return f"Error: {detail}"
            except requests.exceptions.RequestException as e:
                if attempt < max_retries:
                    logger.warning(f"OpenRouter query failed (attempt {attempt + 1}/{max_retries + 1}), retrying... Error: {e}")
                    continue
                else:
                    logger.error(f"OpenRouter query failed after {max_retries + 1} attempts: {e}")
                    return f"Error: {e}"
            except Exception as e:
                if attempt < max_retries:
                    logger.warning(f"OpenRouter query failed (attempt {attempt + 1}/{max_retries + 1}), retrying... Error: {e}")
                    continue
                else:
                    logger.error(f"OpenRouter query failed after {max_retries + 1} attempts: {e}")
                    return f"Error: {e}"
        
        # This should never be reached, but just in case
        return "Error: Unexpected retry loop exit"
        
    def _extract_text_response(self, response_data: Dict[str, Any]) -> str:
        """
        Extracts the textual response from an OpenRouter API response in a consistent way,
        handling reasoning-enabled models, encrypted reasoning, and structured outputs.
        
        Args:
            response_data: Raw JSON response from OpenRouter API.
        
        Returns:
            Extracted text as a single string, or an error message if no text found.
        """
        try:
            text_pieces = []

            # Prefer iterating over the 'output' array
            for item in response_data.get("output", []):
                # Messages from assistant
                if item.get("type") == "message":
                    for content in item.get("content", []):
                        if content.get("type") == "output_text" and content.get("text"):
                            text_pieces.append(content["text"])

                # Reasoning outputs: skip so returned value is only the assistant message (JSON).
                # Some models (e.g. GPT-5) return summary as list of dicts, which would break join().
                elif item.get("type") == "reasoning":
                    pass

            # Fallback for legacy 'choices'
            if not text_pieces and "choices" in response_data:
                for choice in response_data.get("choices", []):
                    message = choice.get("message", {})
                    content = message.get("content")
                    if isinstance(content, str) and content.strip():
                        text_pieces.append(content.strip())
            
            if not text_pieces:
                # Surface provider failures (e.g. capacity) instead of a vague empty-output error
                err = response_data.get("error") or {}
                if isinstance(err, dict) and err.get("message"):
                    return f"Error: {err.get('code', 'provider_error')}: {err['message']}"
                if response_data.get("status") == "failed":
                    return f"Error: OpenRouter response status=failed: {response_data}"
                return "Error: No text found in model response"

            # Concatenate all pieces and return
            return "\n".join(text_pieces).strip()

        except Exception as e:
            return f"Error: Failed to extract text - {e}"
