import os
import json
import openai
import requests
import anthropic
from django.conf import settings
from google import genai
from google.genai.types import (
    FunctionDeclaration,
    GenerateContentConfig,
    HttpOptions,
    Tool,
)
from .ai_tools import tools as ai_tools
from projects.utils.app_functions import app_functions
import traceback # Import traceback for better error logging

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
    
    def generate_stream(self, messages, project_id):
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
    
    def generate_stream(self, messages, project_id):
        current_messages = list(messages) # Work on a copy
        
        while True: # Loop to handle potential multi-turn tool calls (though typically one round)
            try:
                params = {
                    "model": self.model,
                    "messages": current_messages,
                    "stream": True,
                    "tool_choice": "auto", 
                    "tools": ai_tools 
                }
                
                print(f"\n[OpenAIProvider Debug] Making API call with {len(current_messages)} messages.")
                # Add detailed logging of the messages before the call
                try:
                    print(f"[OpenAIProvider Debug] Messages content:\n{json.dumps(current_messages, indent=2)}")
                except Exception as log_e:
                    print(f"[OpenAIProvider Debug] Error logging messages: {log_e}") # Handle potential logging errors
                
                response_stream = self.client.chat.completions.create(**params)
                
                # Variables for this specific API call
                tool_calls_requested = [] # Stores {id, function_name, function_args_str}
                full_assistant_message = {"role": "assistant", "content": None, "tool_calls": []} # To store the complete assistant turn
                
                # --- Process the stream from the API --- 
                for chunk in response_stream:
                    delta = chunk.choices[0].delta if chunk.choices else None
                    finish_reason = chunk.choices[0].finish_reason if chunk.choices else None

                    if not delta: continue # Skip empty chunks

                    # --- Accumulate Text Content --- 
                    if delta.content:
                        yield delta.content # Stream text content immediately
                        if full_assistant_message["content"] is None:
                            full_assistant_message["content"] = ""
                        full_assistant_message["content"] += delta.content

                    # --- Accumulate Tool Call Details --- 
                    if delta.tool_calls:
                        for tool_call_chunk in delta.tool_calls:
                            # Find or create the tool call entry
                            tc_index = tool_call_chunk.index
                            while len(tool_calls_requested) <= tc_index:
                                tool_calls_requested.append({"id": None, "type": "function", "function": {"name": None, "arguments": ""}})
                            
                            current_tc = tool_calls_requested[tc_index]
                            
                            if tool_call_chunk.id:
                                current_tc["id"] = tool_call_chunk.id
                            if tool_call_chunk.function:
                                if tool_call_chunk.function.name:
                                    current_tc["function"]["name"] = tool_call_chunk.function.name
                                if tool_call_chunk.function.arguments:
                                    current_tc["function"]["arguments"] += tool_call_chunk.function.arguments

                    # --- Check Finish Reason --- 
                    if finish_reason:
                        # Print the finish reason as soon as it's detected
                        print(f"\n>>> [OpenAIProvider Debug] Finish Reason Detected: {finish_reason} <<<") 
                        
                        if finish_reason == "tool_calls":
                            # Store the completed tool call requests in the assistant message
                            full_assistant_message["tool_calls"] = tool_calls_requested
                            # Don't yield content if it was just tool calls
                            if full_assistant_message["content"] is None:
                                 full_assistant_message.pop("content") 
                                 
                            current_messages.append(full_assistant_message) # Add assistant's request message
                            
                            # --- Execute Tools and Prepare Next Call --- 
                            tool_results_messages = []
                            for tool_call_to_execute in tool_calls_requested:
                                tool_call_id = tool_call_to_execute["id"]
                                tool_call_name = tool_call_to_execute["function"]["name"]
                                tool_call_args_str = tool_call_to_execute["function"]["arguments"]
                                
                                print(f"\n[OpenAIProvider Debug] Executing Tool: {tool_call_name} (ID: {tool_call_id})")
                                print(f"[OpenAIProvider Debug] Raw Args: {tool_call_args_str}")
                                
                                result_content = ""
                                notification_data = None
                                try:
                                    parsed_args = json.loads(tool_call_args_str)
                                    tool_result = app_functions(tool_call_name, parsed_args, project_id)
                                    
                                    # Handle the case where tool_result is a dict with notification data
                                    if isinstance(tool_result, dict) and tool_result.get("is_notification") is True:
                                        # Set notification data to be yielded later
                                        notification_data = {
                                            "is_notification": True,
                                            "notification_type": tool_result.get("notification_type", "features")
                                        }
                                        # Use the message_to_agent as the result content
                                        result_content = str(tool_result.get("message_to_agent", ""))
                                    else:
                                        # Normal case without notification or when tool_result is a string
                                        if isinstance(tool_result, str):
                                            result_content = tool_result
                                        else:
                                            result_content = str(tool_result.get("message_to_agent", ""))
                                    
                                    print(f"[OpenAIProvider Debug] Tool Success. Result: {result_content}")
                                except json.JSONDecodeError as e:
                                    error_message = f"Failed to parse JSON arguments: {e}. Args: {tool_call_args_str}"
                                    print(f"[OpenAIProvider Error] {error_message}")
                                    result_content = f"Error: {error_message}"
                                    notification_data = None
                                except Exception as e:
                                    error_message = f"Error executing tool {tool_call_name}: {e}"
                                    print(f"[OpenAIProvider Error] {error_message}\n{traceback.format_exc()}")
                                    result_content = f"Error: {error_message}"
                                    notification_data = None
                                
                                # Append tool result message
                                tool_results_messages.append({
                                    "role": "tool",
                                    "tool_call_id": tool_call_id,
                                    "name": tool_call_name,
                                    "content": result_content
                                })
                                
                                # If we have notification data, yield it to the consumer
                                if notification_data:
                                    yield json.dumps(notification_data)
                                
                            current_messages.extend(tool_results_messages) # Add tool results
                            # Continue the outer while loop to make the next API call
                            break # Break inner chunk loop
                        
                        elif finish_reason == "stop":
                            # Conversation finished naturally
                            return # Exit the generator completely
                        else:
                            # Handle other finish reasons if necessary (e.g., length, content_filter)
                            print(f"[OpenAIProvider Warning] Unhandled finish reason: {finish_reason}")
                            return # Exit generator
                
                # If the inner loop finished because of tool_calls, the outer loop continues
                if finish_reason == "tool_calls":
                    continue # Go to next iteration of the while True loop for the next API call
                else:
                     # If the loop finished without a finish_reason (shouldn't happen with stream=True)
                     # or if finish_reason was something else unexpected that didn't return/continue
                     print("[OpenAIProvider Warning] Stream ended unexpectedly.")
                     return # Exit generator

            except Exception as e:
                print(f"[OpenAIProvider Critical Error] {str(e)}\n{traceback.format_exc()}")
                yield f"Error with OpenAI stream: {str(e)}"
                return # Exit generator on critical error


class AnthropicProvider(AIProvider):
    """Anthropic Claude provider implementation"""
    
    def __init__(self):
        api_key = os.getenv('ANTHROPIC_API_KEY')
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY environment variable is not set. Please check your .env file.")
        
        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = "claude-3-7-sonnet-20250219"
    
    def generate_stream(self, messages, project_id):
        try:
            # Convert from OpenAI format to Anthropic format
            system_message = next((m['content'] for m in messages if m['role'] == 'system'), None)
            
            # Filter out system messages as Anthropic handles them differently
            anthropic_messages = []
            for m in messages:
                if m['role'] == 'system':
                    continue
                elif m['role'] == 'assistant' and 'tool_calls' in m:
                    # Handle tool calls in the conversation history
                    tool_calls = m.get('tool_calls', [])
                    for tool_call in tool_calls:
                        anthropic_messages.append({
                            "role": "assistant",
                            "content": "",
                            "tool_use": {
                                "name": tool_call.get('function', {}).get('name', ''),
                                "input": json.loads(tool_call.get('function', {}).get('arguments', '{}'))
                            }
                        })
                else:
                    anthropic_messages.append({
                        "role": "user" if m["role"] == "user" else "assistant", 
                        "content": m["content"]
                    })
            
            # Prepare request parameters
            params = {
                "model": self.model,
                "messages": anthropic_messages,
                "max_tokens": 1024
            }
            
            # Add system message if present
            if system_message:
                params["system"] = system_message

            tools = ai_tools
            
            # Add tools if provided
            if tools:
                # Convert OpenAI tool format to Anthropic tool format
                anthropic_tools = []
                for tool in tools:
                    if tool.get("type") == "function":
                        function_def = tool["function"]
                        anthropic_tools.append({
                            "name": function_def["name"],
                            "description": function_def.get("description", ""),
                            "input_schema": function_def.get("parameters", {})
                        })
                
                if anthropic_tools:
                    params["tools"] = anthropic_tools
            
            # Create streaming response
            tool_use_detected = False
            current_tool_use = None
            
            with self.client.messages.stream(**params) as stream:
                for chunk in stream:
                    # Check for text content
                    if hasattr(chunk, 'delta') and hasattr(chunk.delta, 'text') and chunk.delta.text:
                        yield chunk.delta.text
                    
                    # Check for tool use
                    if hasattr(chunk, 'delta') and hasattr(chunk.delta, 'tool_use'):
                        tool_use_detected = True
                        # When we receive the first tool_use delta
                        if chunk.delta.tool_use and hasattr(chunk.delta.tool_use, 'name'):
                            current_tool_use = {
                                "name": chunk.delta.tool_use.name,
                                "input": {}  # Will be built up over multiple chunks
                            }
                        
                        # Update input as we receive chunks
                        if chunk.delta.tool_use and hasattr(chunk.delta.tool_use, 'input'):
                            if current_tool_use:
                                # Merge any new input fields
                                if isinstance(chunk.delta.tool_use.input, dict):
                                    current_tool_use["input"].update(chunk.delta.tool_use.input)
                    
                    # When the chunk type is 'message_stop' and we detected tool use, 
                    # emit the complete tool call
                    if chunk.type == 'message_stop' and tool_use_detected and current_tool_use:
                        yield json.dumps({
                            "tool_call": {
                                "name": current_tool_use["name"],
                                "arguments": current_tool_use["input"]
                            }
                        })
                        
        except Exception as e:
            yield f"Error with Anthropic: {str(e)}"


class GoogleAIProvider(AIProvider):
    """Google AI provider implementation"""
    
    def __init__(self):
        api_key = os.getenv('GEMINI_API_KEY')
        if not api_key:
            raise ValueError("GEMINI_API_KEY environment variable is not set. Please check your .env file.")
        
        # Initialize the Google Generative AI client
        # genai.configure(api_key=api_key)
        self.client = genai.Client(api_key=api_key)
        self.model_id = "gemini-2.5-pro-exp-03-25"  # Using Gemini 2.0 Flash as default
    
    def generate_stream(self, messages, project_id):
        try:
            # Convert from OpenAI format to Google format
            google_contents = []
            system_message = None
            
            # Extract system message if present
            for m in messages:
                if m["role"] == "system":
                    system_message = m["content"]
                    break
            
            # Convert remaining messages to Google format
            for m in messages:
                if m["role"] == "system":
                    continue
                
                role = "user" if m["role"] == "user" else "model"
                if m["role"] == "user" and system_message and not google_contents:
                    # Add system message as a preamble to the first user message
                    google_contents.append({
                        "role": role,
                        "parts": [{"text": f"{system_message}\n\n{m['content']}"}]
                    })
                elif m["role"] == "assistant" and "tool_calls" in m:
                    # Handle tool calls in the conversation history
                    content_parts = []
                    if m["content"]:
                        content_parts.append({"text": m["content"]})
                    
                    # Add function calls
                    for tool_call in m.get("tool_calls", []):
                        if "function" in tool_call:
                            function_call = {
                                "name": tool_call["function"]["name"],
                                "args": json.loads(tool_call["function"]["arguments"])
                            }
                            content_parts.append({"function_call": function_call})
                    
                    google_contents.append({
                        "role": role,
                        "parts": content_parts
                    })
                else:
                    google_contents.append({
                        "role": role,
                        "parts": [{"text": m["content"]}]
                    })
            
            # Prepare configuration
            config = {}

            tools = ai_tools
            
            # Add tools if provided
            if tools:
                google_tools = []
                for tool in tools:
                    if tool.get("type") == "function":
                        function_def = tool["function"]
                        # Convert parameters to uppercase types as required by Google API
                        parameters = self._convert_json_schema_types(function_def.get("parameters", {}))
                        
                        function_declaration = FunctionDeclaration(
                            name=function_def["name"],
                            description=function_def.get("description", ""),
                            parameters=parameters
                        )
                        google_tools.append(Tool(function_declarations=[function_declaration]))
                
                if google_tools:
                    config["tools"] = google_tools
            
            # Add temperature and other generation config options
            # config["temperature"] = 0.7
            config["max_output_tokens"] = 1024
            
            # Create the generation config
            generation_config = GenerateContentConfig(**config)
            
            # Get the model
            # model = self.client.models.get(self.model_id)
            client = self.client
            
            # Generate content with streaming
            stream = client.models.generate_content_stream(
                model=self.model_id,
                contents=google_contents,
                config=generation_config
            )
            
            # Process the streaming response
            for chunk in stream:
                # Check for text responses
                if hasattr(chunk, 'candidates') and chunk.candidates:
                    for candidate in chunk.candidates:
                        if hasattr(candidate, 'content') and candidate.content:
                            for part in candidate.content.parts:
                                if hasattr(part, 'text') and part.text:
                                    yield part.text
                
                # Check for function calls
                if hasattr(chunk, 'candidates') and chunk.candidates:
                    for candidate in chunk.candidates:
                        if hasattr(candidate, 'function_calls') and candidate.function_calls:
                            for function_call in candidate.function_calls:
                                yield json.dumps({
                                    "tool_call": {
                                        "name": function_call.name,
                                        "arguments": function_call.args
                                    }
                                })
        
        except Exception as e:
            yield f"Error with Google AI: {str(e)}"
    
    def _convert_json_schema_types(self, schema):
        """Convert JSON schema types to Google's format (uppercase types)"""
        if not schema:
            return schema
            
        result = schema.copy()
        
        # Use dictionary mapping instead of if-elif chains
        type_map = {
            "object": "OBJECT",
            "array": "ARRAY",
            "string": "STRING",
            "number": "NUMBER",
            "integer": "INTEGER",
            "boolean": "BOOLEAN",
            "null": "NULL"
        }
        
        # Convert type values to uppercase
        if "type" in result:
            result["type"] = type_map.get(result["type"], result["type"])
        
        # Recursively convert nested properties
        if "properties" in result and isinstance(result["properties"], dict):
            for prop_name, prop_schema in result["properties"].items():
                result["properties"][prop_name] = self._convert_json_schema_types(prop_schema)
        
        # Convert array item types
        if "items" in result and isinstance(result["items"], dict):
            result["items"] = self._convert_json_schema_types(result["items"])
        
        return result 