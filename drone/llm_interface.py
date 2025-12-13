"""
LLM Interface for DeepDrone supporting LiteLLM and Ollama.
"""

import os
from typing import List, Dict, Any, Optional
import json
import logging

from .config import ModelConfig

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class LLMInterface:
    """Interface for interacting with various LLM providers."""
    
    def __init__(self, model_config: ModelConfig):
        self.model_config = model_config
        self._setup_client()
    
    def _setup_client(self):
        """Set up the appropriate client based on model provider."""
        if self.model_config.provider == "ollama":
            self._setup_ollama()
        else:
            self._setup_litellm()
    
    def _setup_ollama(self):
        """Set up Ollama client."""
        try:
            import ollama
            self.client = ollama
            self.client_type = "ollama"
            
            # Test connection
            try:
                models = self.client.list()
                available_models = models.models if hasattr(models, 'models') else []
                logger.info(f"Connected to Ollama. Available models: {len(available_models)}")
                
                # Check if the requested model is available
                model_names = [model.model for model in available_models]
                if self.model_config.model_id not in model_names:
                    logger.warning(f"Model '{self.model_config.model_id}' not found locally. Available models: {model_names}")
                    
            except Exception as e:
                logger.warning(f"Could not connect to Ollama: {e}")
                logger.info("Make sure Ollama is running: ollama serve")
                
        except ImportError:
            raise ImportError("Ollama package not installed. Install with: pip install ollama")
    
    def _setup_litellm(self):
        """Set up LiteLLM client."""
        try:
            import litellm
            
            # Set API key in environment if provided (skip for local/placeholder keys)
            if self.model_config.api_key and self.model_config.api_key != "local":
                if self.model_config.provider == "openai":
                    os.environ["OPENAI_API_KEY"] = self.model_config.api_key
                elif self.model_config.provider == "anthropic":
                    os.environ["ANTHROPIC_API_KEY"] = self.model_config.api_key
                elif self.model_config.provider == "mistral":
                    os.environ["MISTRAL_API_KEY"] = self.model_config.api_key
                elif self.model_config.provider == "vertex_ai":
                    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = self.model_config.api_key
            
            # Set base URL if provided
            if self.model_config.base_url:
                litellm.api_base = self.model_config.base_url
            
            self.client = litellm
            self.client_type = "litellm"
            
            logger.info(f"Set up LiteLLM for {self.model_config.provider}")
            
        except ImportError:
            raise ImportError("LiteLLM package not installed. Install with: pip install litellm")
    
    def chat(self, messages: List[Dict[str, str]]) -> str:
        """Send chat messages and get response."""
        try:
            if self.client_type == "ollama":
                return self._chat_ollama(messages)
            else:
                return self._chat_litellm(messages)
        except Exception as e:
            logger.error(f"Chat error: {e}")
            return f"Error communicating with {self.model_config.provider}: {str(e)}"
    
    def chat_with_metadata(self, messages: List[Dict[str, str]]) -> Dict[str, Any]:
        """Send chat messages and get response with metadata (thinking, timing, etc.)."""
        try:
            if self.client_type == "ollama":
                return self._chat_ollama_with_metadata(messages)
            else:
                # LiteLLM doesn't have thinking/metadata, just return content
                content = self._chat_litellm(messages)
                return {"content": content}
        except Exception as e:
            logger.error(f"Chat error: {e}")
            return {
                "content": f"Error communicating with {self.model_config.provider}: {str(e)}"
            }
    
    def _chat_ollama(self, messages: List[Dict[str, str]]) -> str:
        """Chat using Ollama (returns only the response text)."""
        metadata = self._chat_ollama_with_metadata(messages)
        return metadata.get("content", "")
    
    def _chat_ollama_with_metadata(self, messages: List[Dict[str, str]]) -> Dict[str, Any]:
        """Chat using Ollama with full metadata."""
        try:
            # Convert messages to Ollama format
            prompt = self._messages_to_prompt(messages)

            logger.info(f"Sending to Ollama model '{self.model_config.model_id}' (prompt length: {len(prompt)})")

            response = self.client.generate(
                model=self.model_config.model_id,
                prompt=prompt,
                options={
                    'temperature': self.model_config.temperature,
                    'num_predict': self.model_config.max_tokens,
                }
            )

            logger.info(f"Ollama response type: {type(response)}")
            logger.info(f"Ollama response has attributes: {hasattr(response, 'response')}, {hasattr(response, 'thinking')}, {hasattr(response, 'context')}")
            
            # Extract data from Ollama GenerateResponse object
            # The response object has: response, thinking, context, and other metadata
            if hasattr(response, 'response'):
                # It's an Ollama GenerateResponse object
                main_response = response.response if response.response else ''
                thinking = response.thinking if hasattr(response, 'thinking') and response.thinking else ''
                
                # Get timing info
                eval_duration = getattr(response, 'eval_duration', 0)
                thinking_time = round(eval_duration / 1_000_000_000, 1) if eval_duration else 0
                
                logger.info(f"Extracted from GenerateResponse: response_len={len(main_response)}, thinking_len={len(thinking)}, time={thinking_time}s")
            elif isinstance(response, dict):
                # It's a dict (older Ollama versions or different API)
                main_response = response.get('response', '')
                thinking = response.get('thinking', '')
                eval_duration = response.get('eval_duration', 0)
                thinking_time = round(eval_duration / 1_000_000_000, 1) if eval_duration else 0
                
                logger.info(f"Extracted from dict: response_len={len(main_response)}, thinking_len={len(thinking)}, time={thinking_time}s")
            else:
                # Unexpected format - log and convert to string
                logger.error(f"Unexpected Ollama response type: {type(response)}")
                logger.error(f"Response value: {str(response)[:500]}")
                main_response = str(response)
                thinking = ''
                thinking_time = 0

            logger.info(f"Main response length: {len(main_response)}, Thinking length: {len(thinking)}, Time: {thinking_time}s")
            logger.info(f"Main response preview: {main_response[:200] if main_response else 'EMPTY'}")

            # Handle reasoning models (like qwen3) that put everything in thinking field
            if not main_response and thinking:
                logger.info("Response field is empty, extracting answer from thinking field")
                # The thinking contains the reasoning process
                # We'll use it as-is for now, but store it as thinking
                # The actual final answer is usually at the end or marked
                
                # Try to extract just the final answer if there's a clear pattern
                final_answer = self._extract_final_answer(thinking)
                
                if final_answer and len(final_answer) < len(thinking) * 0.8:
                    # We found a concise answer
                    main_response = final_answer
                    # Keep full thinking for the collapsible section
                else:
                    # No clear answer extraction, use the whole thinking as response
                    # This means the UI will show the full reasoning
                    main_response = thinking
                    # Don't duplicate thinking in metadata
                    thinking = ""

            if not main_response:
                logger.warning("Empty response from Ollama!")
                main_response = "The AI model returned an empty response. Please try again."

            # Prepare result - ONLY include the actual response text
            result = {"content": main_response.strip()}
            
            # Add thinking metadata if available and different from main response
            if thinking and thinking != main_response:
                result["thinking"] = thinking.strip()
                result["thinking_time"] = thinking_time

            logger.info(f"Returning result with content length: {len(result['content'])}, has_thinking: {bool(thinking)}")
            return result
            
        except Exception as e:
            error_str = str(e).lower()
            
            if "model not found" in error_str or "model does not exist" in error_str:
                available_models = []
                try:
                    models = self.client.list()
                    available_models = [m.model for m in models.models] if hasattr(models, 'models') else []
                except:
                    pass
                
                error_msg = f"❌ Model '{self.model_config.model_id}' not found in Ollama.\n\n"
                
                if available_models:
                    error_msg += f"📋 Available local models:\n"
                    for model in available_models:
                        error_msg += f"  • {model}\n"
                    error_msg += f"\n💡 To install {self.model_config.model_id}, run:\n"
                    error_msg += f"   ollama pull {self.model_config.model_id}\n"
                else:
                    error_msg += "📭 No models found locally.\n\n"
                    error_msg += f"💡 To install {self.model_config.model_id}, run:\n"
                    error_msg += f"   ollama pull {self.model_config.model_id}\n\n"
                    error_msg += "🎯 Popular models to try:\n"
                    error_msg += "   • ollama pull llama3.1\n"
                    error_msg += "   • ollama pull codestral\n"
                    error_msg += "   • ollama pull qwen2.5-coder\n"
                
                return {"content": error_msg}
            
            elif "connection" in error_str or "refused" in error_str:
                return {"content": "❌ Cannot connect to Ollama.\n\n💡 Make sure Ollama is running:\n   ollama serve\n\n📥 Download Ollama from: https://ollama.com/download"}
            
            return {"content": f"❌ Ollama error: {str(e)}"}
    
    def _extract_final_answer(self, thinking: str) -> str:
        """Extract the final answer from thinking/reasoning text."""
        # Common patterns for final answers in reasoning models
        patterns = [
            "Final answer:",
            "Therefore,",
            "So the answer is",
            "The result is",
            "EXECUTE_FUNCTION:",  # For function calls
        ]
        
        thinking_lower = thinking.lower()
        
        # Look for function calls first
        if "execute_function:" in thinking_lower:
            # This is a function call, return the whole thing
            return thinking
        
        # Look for explicit answer markers
        for pattern in patterns:
            if pattern.lower() in thinking_lower:
                # Find the position and extract from there
                idx = thinking_lower.find(pattern.lower())
                if idx != -1:
                    answer = thinking[idx:].strip()
                    # Take the first paragraph after the marker
                    lines = answer.split('\n')
                    # Take up to 5 lines or until empty line
                    result_lines = []
                    for line in lines[:10]:
                        if line.strip():
                            result_lines.append(line)
                        elif result_lines:  # Empty line after content
                            break
                    if result_lines:
                        return '\n'.join(result_lines)
        
        # No clear pattern found, return empty to use full thinking
        return ""
    
    def _chat_litellm(self, messages: List[Dict[str, str]]) -> str:
        """Chat using LiteLLM."""
        try:
            response = self.client.completion(
                model=self.model_config.model_id,
                messages=messages,
                max_tokens=self.model_config.max_tokens,
                temperature=self.model_config.temperature,
            )
            
            return response.choices[0].message.content
            
        except Exception as e:
            if "api key" in str(e).lower():
                return f"API key error for {self.model_config.provider}. Please set your API key with: deepdrone models set-key {self.model_config.name}"
            elif "quota" in str(e).lower() or "billing" in str(e).lower():
                return f"Billing/quota error for {self.model_config.provider}. Please check your account."
            elif "model" in str(e).lower() and "not found" in str(e).lower():
                return f"Model '{self.model_config.model_id}' not found for {self.model_config.provider}."
            
            raise e
    
    def _messages_to_prompt(self, messages: List[Dict[str, str]]) -> str:
        """Convert messages to a single prompt for models that don't support chat format."""
        prompt_parts = []
        
        for message in messages:
            role = message["role"]
            content = message["content"]
            
            if role == "system":
                prompt_parts.append(f"System: {content}")
            elif role == "user":
                prompt_parts.append(f"Human: {content}")
            elif role == "assistant":
                prompt_parts.append(f"Assistant: {content}")
        
        prompt_parts.append("Assistant: ")
        
        return "\n\n".join(prompt_parts)
    
    def test_connection(self) -> Dict[str, Any]:
        """Test connection to the LLM service."""
        try:
            test_messages = [
                {"role": "user", "content": "Hello, please respond with 'Connection test successful'"}
            ]
            
            response = self.chat(test_messages)
            
            return {
                "success": True,
                "response": response,
                "provider": self.model_config.provider,
                "model": self.model_config.model_id
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "provider": self.model_config.provider,
                "model": self.model_config.model_id
            }
    
    def get_model_info(self) -> Dict[str, Any]:
        """Get information about the current model."""
        info = {
            "name": self.model_config.name,
            "provider": self.model_config.provider,
            "model_id": self.model_config.model_id,
            "max_tokens": self.model_config.max_tokens,
            "temperature": self.model_config.temperature,
            "client_type": self.client_type,
        }
        
        if self.model_config.base_url:
            info["base_url"] = self.model_config.base_url
        
        return info