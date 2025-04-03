import os
import json
import openai
import requests
from django.conf import settings

class AIProvider:
    """Base class for AI providers"""
    
    @staticmethod
    def get_provider(provider_name):
        """Factory method to get the appropriate provider"""
        # provider_name = "anthropic"
        providers = {
            'openai': OpenAIProvider,
            'anthropic': AnthropicProvider,
            'google': GoogleAIProvider
        }
        return providers.get(provider_name, OpenAIProvider)()
    
    def generate_stream(self, messages):
        """Generate streaming response from the AI provider"""
        raise NotImplementedError("Subclasses must implement this method")


class OpenAIProvider(AIProvider):
    """OpenAI provider implementation"""
    
    def __init__(self):
        api_key = os.getenv('OPENAI_API_KEY')
        if not api_key:
            raise ValueError("OPENAI_API_KEY environment variable is not set. Please check your .env file.")
        
        # Initialize OpenAI client without proxies parameter
        # This is compatible with newer versions of the OpenAI library
        self.client = openai.OpenAI(api_key=api_key)
        self.model = "gpt-4o"
    
    def generate_stream(self, messages):
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                stream=True
            )
            
            for chunk in response:
                if chunk.choices and chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
        except Exception as e:
            yield f"Error with OpenAI: {str(e)}"


class AnthropicProvider(AIProvider):
    """Anthropic Claude provider implementation"""
    
    def __init__(self):
        self.api_key = os.getenv('ANTHROPIC_API_KEY')
        self.model = "claude-3-7-sonnet-20250219"
        self.api_url = "https://api.anthropic.com/v1/messages"
    
    def generate_stream(self, messages):
        try:
            # Convert from OpenAI format to Anthropic format
            system_message = next((m['content'] for m in messages if m['role'] == 'system'), None)
            
            # Filter out system messages as Anthropic handles them differently
            anthropic_messages = [
                {"role": "user" if m["role"] == "user" else "assistant", "content": m["content"]}
                for m in messages if m["role"] != "system"
            ]
            
            headers = {
                "x-api-key": self.api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json"
            }
            
            data = {
                "model": self.model,
                "messages": anthropic_messages,
                "system": system_message,
                "stream": True,
                "max_tokens": 1024
            }
            
            response = requests.post(
                self.api_url,
                headers=headers,
                json=data,
                stream=True
            )
            
            for line in response.iter_lines():
                if line:
                    if line.startswith(b"data: "):
                        data_str = line[6:].decode('utf-8')
                        if data_str.strip() == "[DONE]":
                            break
                        try:
                            data_json = json.loads(data_str)
                            if data_json.get("type") == "content_block_delta" and data_json.get("delta", {}).get("text"):
                                yield data_json["delta"]["text"]
                        except json.JSONDecodeError:
                            continue
        except Exception as e:
            yield f"Error with Anthropic: {str(e)}"


class GoogleAIProvider(AIProvider):
    """Google AI provider implementation"""
    
    def __init__(self):
        self.api_key = os.getenv('GEMINI_API_KEY')
        self.model = "gemini-flash-2.0"
        self.api_url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:streamGenerateContent"
    
    def generate_stream(self, messages):
        try:
            # Convert from OpenAI format to Google format
            google_messages = []
            
            for msg in messages:
                role = "user" if msg["role"] == "user" else "model"
                if msg["role"] == "system":
                    # Prepend system message to the first user message
                    continue
                
                google_messages.append({
                    "role": role,
                    "parts": [{"text": msg["content"]}]
                })
            
            # Add system message as a preamble to the first user message if it exists
            system_message = next((m['content'] for m in messages if m['role'] == 'system'), None)
            if system_message and google_messages:
                for i, msg in enumerate(google_messages):
                    if msg["role"] == "user":
                        google_messages[i]["parts"][0]["text"] = f"{system_message}\n\n{msg['parts'][0]['text']}"
                        break
            
            params = {
                "key": self.api_key
            }
            
            headers = {
                "Content-Type": "application/json"
            }
            
            data = {
                "contents": google_messages,
                "generationConfig": {
                    "temperature": 0.7,
                    "maxOutputTokens": 1024
                }
            }
            
            response = requests.post(
                self.api_url,
                headers=headers,
                params=params,
                json=data,
                stream=True
            )
            
            for line in response.iter_lines():
                if line:
                    try:
                        data_json = json.loads(line)
                        if "candidates" in data_json and data_json["candidates"]:
                            for candidate in data_json["candidates"]:
                                if "content" in candidate and "parts" in candidate["content"]:
                                    for part in candidate["content"]["parts"]:
                                        if "text" in part:
                                            yield part["text"]
                    except json.JSONDecodeError:
                        continue
        except Exception as e:
            yield f"Error with Google AI: {str(e)}" 