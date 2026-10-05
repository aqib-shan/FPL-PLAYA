"""
Unified LLM Engine for Gemini API communication
"""

import logging
from typing import Optional

from google import genai
from google.genai import types

from ..core.config import Config

logger = logging.getLogger(__name__)


class LLMEngine:
    """
    Unified LLM engine that works with any Gemini model configuration.
    
    This class handles:
    - Gemini API initialization and configuration
    - Web search integration when enabled
    - Response processing and JSON extraction
    - Error handling for LLM operations
    """
    
    def __init__(self, config: Config, model_name: str):
        """
        Initialize LLM engine.
        
        Args:
            config: Main FPL configuration
            model_name: Name of the model config to use (e.g., "main", "lightweight")
        """
        self.config = config
        
        # Get the model config dynamically from the config file
        self.llm_config = config.get_llm_model_config(model_name)
        self.model_name = self.llm_config.get('model')
        
        # Initialize Gemini client and model
        self._initialize_gemini_model()
    
    def _initialize_gemini_model(self):
        """Initialize the Gemini client and model configuration"""
        try:
            api_key = self.llm_config.get('api_key')
            
            client = genai.Client(api_key=api_key)

            # Define the grounding tool for web search
            grounding_tool = types.Tool(
                google_search=types.GoogleSearch()
            )

            # Configure generation settings from model config
            generation_config = types.GenerateContentConfig(
                tools=[grounding_tool],  # Re-enabled web search grounding
                temperature=self.llm_config.get('temperature', 0.3),
                max_output_tokens=self.llm_config.get('max_output_tokens', 8192),
                top_p=self.llm_config.get('top_p', 0.8),
                top_k=self.llm_config.get('top_k', 25),
                # response_mime_type="application/json",      # Can't use for now as doesn't work with web search
            )
            
            # Store client and config for later use
            self.client = client
            self.generation_config = generation_config
            
            logger.info(f"Initialized LLM engine with model: {self.model_name}")
            
        except Exception as e:
            logger.error(f"Failed to initialize Gemini model: {e}")
            raise
    
    def query(self, prompt: str, response_schema: Optional[dict] = None, max_retries: Optional[int] = None) -> str:
        """
        Query the LLM with a given prompt and automatic retry on failure.
        
        Args:
            prompt: The prompt to send to the LLM
            response_schema: Optional response schema to use for the LLM response
            max_retries: Maximum number of retry attempts (defaults to config value if None)

        Returns:
            String containing the LLM response
        """
        # Use config value if max_retries not specified
        if max_retries is None:
            max_retries = self.llm_config.get('max_retries', 1)
        
        for attempt in range(max_retries + 1):
            try:
                # Initialize the model if not already done
                if not hasattr(self, 'client'):
                    self._initialize_gemini_model()

                generation_config = self.generation_config.model_copy()
                if response_schema:
                    generation_config.response_schema = response_schema
                    
                response = self.client.models.generate_content(
                    model=self.model_name,
                    contents=prompt,
                    config=generation_config
                )
                
                # Extract the response text
                text_response = self._extract_json_response(response)
                
                # Check if extraction failed
                if text_response.startswith("Error:"):
                    if attempt < max_retries:
                        logger.warning(f"LLM response extraction failed (attempt {attempt + 1}/{max_retries + 1}), retrying...")
                        logger.warning(f"Error: {text_response}")
                        continue  # Try again
                    else:
                        logger.error(f"LLM response extraction failed after {max_retries + 1} attempts")
                        return text_response
                
                # Success!
                if attempt > 0:
                    logger.info(f"LLM query succeeded on retry attempt {attempt + 1}")
                return text_response
                
            except Exception as e:
                if attempt < max_retries:
                    logger.warning(f"LLM query failed (attempt {attempt + 1}/{max_retries + 1}), retrying... Error: {e}")
                    continue
                else:
                    logger.error(f"LLM query failed after {max_retries + 1} attempts: {e}")
                    return f"Error: {e}"
        
        # This should never be reached, but just in case
        return "Error: Unexpected retry loop exit"
        
    def _extract_json_response(self, response: types.GenerateContentResponse) -> str:
        """
        Extract text response from response object.
        
        Args:
            response: Response object
            
        Returns:
            Extracted text string, or error message if extraction fails
        """
        if not response or not hasattr(response, "candidates") or len(response.candidates) == 0:
            return "Error: No candidates returned by LLM"
        
        # Usually the first candidate is the main output
        candidate = response.candidates[0]
        
        if not hasattr(candidate, "content") or not hasattr(candidate.content, "parts") or len(candidate.content.parts) == 0:
            return "Error: Candidate has no content parts"
        
        # Extract text from the first part
        output_text = candidate.content.parts[0].text.strip()
        
        if not output_text:
            return "Error: Empty text content in response"
        
        return output_text