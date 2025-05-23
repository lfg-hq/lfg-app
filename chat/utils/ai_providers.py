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
from projects.utils.app_functions import app_functions
from chat.models import AgentRole, ModelSelection
from projects.models import Project
import traceback # Import traceback for better error logging

class AIProvider:
    """Base class for AI providers"""
    
    @staticmethod
    def get_provider(provider_name, selected_model):
        """Factory method to get the appropriate provider"""
        providers = {
            'openai': lambda: OpenAIProvider(selected_model),
            # 'anthropic': lambda: AnthropicProvider(selected_model),
            # 'google': lambda: GoogleAIProvider(selected_model)
        }
        provider_factory = providers.get(provider_name)
        if provider_factory:
            return provider_factory()
        else:
            return OpenAIProvider(selected_model)  # Default fallback
    
    def generate_stream(self, messages, project_id, conversation_id, tools):
        """Generate streaming response from the AI provider"""
        raise NotImplementedError("Subclasses must implement this method")


class OpenAIProvider(AIProvider):
    """OpenAI provider implementation"""
    
    def __init__(self, selected_model):

        print(f"[OpenAIProvider Debug] Selected model: {selected_model}")

        openai_api_key = os.getenv('OPENAI_API_KEY') 
        anthropic_api_key = os.getenv('ANTHROPIC_API_KEY')

        if selected_model == "gpt_4o":
            self.model = "gpt-4o"
            self.client = openai.OpenAI(api_key=openai_api_key)
        elif selected_model == "gpt_4.1":
            self.model = "gpt-4.1"
            self.client = openai.OpenAI(api_key=openai_api_key)
        elif selected_model == "claude_4_sonnet":
            self.model = "claude-sonnet-4-20250514"
            print(f"[OpenAIProvider Debug] Selected model: {self.model}")
            self.client = openai.OpenAI(api_key=anthropic_api_key, base_url="https://api.anthropic.com/v1/")


    def generate_stream(self, messages, project_id, conversation_id, tools):
        current_messages = list(messages) # Work on a copy

        while True: # Loop to handle potential multi-turn tool calls (though typically one round)
            try:
                params = {
                    "model": self.model,
                    "messages": current_messages,
                    "stream": True,
                    "tool_choice": "auto", 
                    "tools": tools
                }
                
                print(f"\n[OpenAIProvider Debug] Making API call with {len(current_messages)} messages.")
                # Add detailed logging of the messages before the call
                # try:
                #     print(f"[OpenAIProvider Debug] Messages content:\n{json.dumps(current_messages, indent=2)}")
                # except Exception as log_e:
                #     print(f"[OpenAIProvider Debug] Error logging messages: {log_e}") # Handle potential logging errors
                
                response_stream = self.client.chat.completions.create(**params)
                
                # Variables for this specific API call
                tool_calls_requested = [] # Stores {id, function_name, function_args_str}
                full_assistant_message = {"role": "assistant", "content": None, "tool_calls": []} # To store the complete assistant turn

                print("New Loop!!")
                
                # --- Process the stream from the API --- 
                for chunk in response_stream:
                    delta = chunk.choices[0].delta if chunk.choices else None
                    finish_reason = chunk.choices[0].finish_reason if chunk.choices else None

                    if not delta: continue # Skip empty chunks

                    # --- Accumulate Text Content --- 
                    if delta.content:
                        yield delta.content # Stream text content immediately
                        if full_assistant_message["content"] is None:
                            full_assistant_message["content"] = "-"
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
                                    # Send early notification as soon as we know the function name
                                    function_name = tool_call_chunk.function.name
                                    current_tc["function"]["name"] = function_name
                                    
                                    # Determine notification type based on function name
                                    notification_type = None
                                    if function_name == "extract_features":
                                        notification_type = "features"
                                    elif function_name == "extract_personas":
                                        notification_type = "personas"
                                    elif function_name == "start_server":
                                        notification_type = "start_server"
                                    elif function_name == "execute_command":
                                        notification_type = "execute_command"
                                    
                                    # Send early notification if it's an extraction function
                                    if notification_type:
                                        print(f"\n\n=== SENDING EARLY NOTIFICATION FOR {function_name} ===")
                                        # Create a notification with a special marker to make it clearly identifiable
                                        early_notification = {
                                            "is_notification": True,
                                            "notification_type": notification_type,
                                            "early_notification": True,
                                            "function_name": function_name,
                                            "notification_marker": "__NOTIFICATION__"  # Special marker
                                        }
                                        notification_json = json.dumps(early_notification)
                                        print(f"Early notification sent: {notification_json}")
                                        print("==========================================\n\n")
                                        # Yield as a special formatted string that can be easily detected
                                        yield f"__NOTIFICATION__{notification_json}__NOTIFICATION__"
                                
                                if tool_call_chunk.function.arguments:
                                    current_tc["function"]["arguments"] += tool_call_chunk.function.arguments

                    # --- Check Finish Reason --- 
                    if finish_reason:
                        # Print the finish reason as soon as it's detected
                        print(f"\n>>> [OpenAIProvider Debug] Finish Reason Detected: {finish_reason} <<<") 
                        
                        if finish_reason == "tool_calls":
                            # ── 1. Final-ise tool_calls_requested ────────────────────────────
                            for tc in tool_calls_requested:
                                # If the model never emitted arguments (or only whitespace),
                                # replace the empty string with a valid empty-object JSON
                                if not tc["function"]["arguments"].strip():
                                    tc["function"]["arguments"] = "{}"

                            # ── 2. Build the assistant message ───────────────────────────────
                            full_assistant_message["tool_calls"] = tool_calls_requested

                            # Remove the content field if it was just tool calls
                            if full_assistant_message["content"] is None:
                                full_assistant_message.pop("content")

                            # ── 3. Append to the running conversation history ────────────────
                            current_messages.append(full_assistant_message)
                            
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
                                    # Handle empty arguments string by defaulting to an empty object
                                    if not tool_call_args_str.strip():
                                        parsed_args = {}
                                        print("[OpenAIProvider Debug] Empty arguments string, defaulting to empty object")
                                    else:
                                        parsed_args = json.loads(tool_call_args_str)
                                        # Check for both possible spellings of "explanation"
                                        explanation = parsed_args.get("explanation", parsed_args.get("explaination", ""))
                                        
                                        if explanation:
                                            print(f"\n\n[OpenAIProvider Debug] Found explanation: {explanation}\n\n")
                                            
                                            # Format the explanation nicely with markdown
                                            formatted_explanation = f"\n\n{explanation}\n\n"
                                            
                                            # Add to the assistant message content
                                            if full_assistant_message.get("content", None) is None:
                                                print(f"\n\n[OpenAIProvider Debug] Setting content to: {formatted_explanation}\n\n")
                                                full_assistant_message["content"] = formatted_explanation
                                            else:
                                                full_assistant_message["content"] += formatted_explanation
                                            
                                            # Yield the explanation immediately so it streams to the frontend
                                            yield "*"
                                    # Log the function call with clean arguments
                                    print(f"[OpenAIProvider Debug] Calling app_functions with {tool_call_name}, {parsed_args}, {project_id}, {conversation_id}")
                                    
                                    # Execute the function with extensive logging and error handling
                                    try:
                                        tool_result = app_functions(tool_call_name, parsed_args, project_id, conversation_id)
                                        print(f"[OpenAIProvider Debug] app_functions call successful for {tool_call_name}")
                                    except Exception as func_error:
                                        print(f"[OpenAIProvider Error] Error calling app_functions: {str(func_error)}")
                                        print(f"[OpenAIProvider Error] Traceback: {traceback.format_exc()}")
                                        # Rethrow to be caught by the outer try-except
                                        raise

                                    print("\n\n\n\nTool Result: ", tool_result)
                                    
                                    # Send special notification for extraction functions regardless of result
                                    if tool_call_name in ["extract_features", "extract_personas"]:
                                        notification_type = "features" if tool_call_name == "extract_features" else "personas"
                                        print(f"\n\n=== FORCING NOTIFICATION FOR {tool_call_name} ===")
                                        notification_data = {
                                            "is_notification": True,
                                            "notification_type": notification_type,
                                            "function_name": tool_call_name,
                                            "notification_marker": "__NOTIFICATION__"
                                        }
                                        print(f"Forced notification: {notification_data}")
                                        print("==========================================\n\n")
                                    
                                    # Handle the case where tool_result is None
                                    if tool_result is None:
                                        result_content = "The function returned no result."
                                    # Handle the case where tool_result is a dict with notification data
                                    elif isinstance(tool_result, dict) and tool_result.get("is_notification") is True:
                                        # Set notification data to be yielded later
                                        print("\n\n=== NOTIFICATION DATA CREATED IN OPENAI PROVIDER ===")
                                        print(f"Tool result: {tool_result}")
                                        
                                        notification_data = {
                                            "is_notification": True,
                                            "notification_type": tool_result.get("notification_type", "features"),
                                            "notification_marker": "__NOTIFICATION__"  # Special marker
                                        }
                                        
                                        print(f"Notification data to be yielded: {notification_data}")
                                        print("==========================================\n\n")
                                        
                                        # Use the message_to_agent as the result content
                                        result_content = str(tool_result.get("message_to_agent", ""))
                                    else:
                                        # Normal case without notification or when tool_result is a string
                                        if isinstance(tool_result, str):
                                            result_content = tool_result
                                        elif isinstance(tool_result, dict):
                                            result_content = str(tool_result.get("message_to_agent", ""))
                                        else:
                                            # If tool_result is neither a string nor a dict
                                            result_content = str(tool_result) if tool_result is not None else ""
                                    
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
                                    "content": f"Tool call {tool_call_name}() completed. {result_content}."
                                })
                                
                                # If we have notification data, yield it to the consumer with the special format
                                if notification_data:
                                    print("\n\n=== YIELDING NOTIFICATION DATA TO CONSUMER ===")
                                    notification_json = json.dumps(notification_data)
                                    print(f"Notification JSON: {notification_json}")
                                    print("============================================\n\n")
                                    yield f"__NOTIFICATION__{notification_json}__NOTIFICATION__"
                                
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


# class AnthropicProvider(AIProvider):
#     """Anthropic Claude provider implementation"""
    
#     def __init__(self):
#         api_key = os.getenv('ANTHROPIC_API_KEY')
#         if not api_key:
#             raise ValueError("ANTHROPIC_API_KEY environment variable is not set. Please check your .env file.")
        
#         self.client = anthropic.Anthropic(api_key=api_key)
#         self.model = "claude-3-7-sonnet-20250219"
    
#     def convert_openai_to_anthropic_tools(self, openai_tools):
#         """Clean conversion from OpenAI tool format to Anthropic tool format"""
#         anthropic_tools = []
        
#         for tool in openai_tools:
#             if tool.get("type") == "function":
#                 function_def = tool["function"]
#                 function_name = function_def["name"]
                
#                 # Create proper Anthropic schema
#                 input_schema = function_def.get("parameters", {}).copy()
                
#                 # Ensure schema has type at top level
#                 if "type" not in input_schema:
#                     input_schema["type"] = "object"
                
#                 # Create Anthropic tool format
#                 anthropic_tool = {
#                     "name": function_name,
#                     "description": function_def.get("description", ""),
#                     "input_schema": input_schema
#                 }
                
#                 anthropic_tools.append(anthropic_tool)
        
#         return anthropic_tools
    
#     def convert_messages_to_anthropic_format(self, messages):
#         """Convert OpenAI message format to Anthropic message format"""
#         anthropic_messages = []
#         system_message = None
        
#         for message in messages:
#             role = message.get("role")
#             content = message.get("content", "")
            
#             if role == "system":
#                 system_message = content
#             elif role == "user":
#                 anthropic_messages.append({"role": "user", "content": content})
#             elif role == "assistant":
#                 if "tool_calls" in message:
#                     # Handle tool calls - convert to Anthropic format
#                     if message.get("content"):
#                         # If there's text content before tool calls, add it as a separate message
#                         anthropic_messages.append({"role": "assistant", "content": message.get("content", "")})
                    
#                     for tool_call in message.get("tool_calls", []):
#                         if tool_call.get("type") == "function":
#                             function = tool_call.get("function", {})
#                             try:
#                                 tool_input = json.loads(function.get("arguments", "{}"))
#                             except json.JSONDecodeError:
#                                 # Handle invalid JSON by creating an empty object
#                                 print(f"[AnthropicProvider Warning] Failed to parse tool arguments: {function.get('arguments')}")
#                                 tool_input = {}
                                
#                             anthropic_messages.append({
#                                 "role": "assistant",
#                                 "content": "",
#                                 "tool_use": {
#                                     "name": function.get("name", ""),
#                                     "input": tool_input
#                                 }
#                             })
#                 else:
#                     anthropic_messages.append({"role": "assistant", "content": content})
#             elif role == "tool":
#                 # Convert tool responses to user messages with clear indication that it's a tool result
#                 tool_content = message.get("content", "")
#                 tool_call_id = message.get("tool_call_id", "")
#                 anthropic_messages.append({"role": "user", "content": f"Tool result for call {tool_call_id}: {tool_content}"})
        
#         return anthropic_messages, system_message
    
#     def process_tool_use_stream(self, stream, project_id):
#         """Process Anthropic stream with tool use functionality"""
#         # Variables to track state
#         full_content = ""
#         tool_use_detected = False
#         current_tool_use = None
#         tool_calls = []
        
#         # Process stream chunks
#         for chunk in stream:
#             # Yield text content for immediate display
#             if hasattr(chunk, 'delta') and hasattr(chunk.delta, 'text') and chunk.delta.text:
#                 content = chunk.delta.text
#                 yield content
#                 full_content += content
            
#             # Process tool use
#             if hasattr(chunk, 'delta') and hasattr(chunk.delta, 'tool_use'):
#                 tool_use_detected = True
#                 tool_delta = chunk.delta.tool_use
                
#                 # Initialize tool use info when we get a name
#                 if tool_delta and hasattr(tool_delta, 'name') and tool_delta.name:
#                     current_tool_use = {
#                         "id": f"call_{len(tool_calls)}",
#                         "name": tool_delta.name,
#                         "input": {}
#                     }
#                     tool_calls.append({
#                         "id": current_tool_use["id"],
#                         "type": "function",
#                         "function": {
#                             "name": current_tool_use["name"],
#                             "arguments": "{}"
#                         }
#                     })
                
#                 # Update input as we receive chunks
#                 if tool_delta and hasattr(tool_delta, 'input') and isinstance(tool_delta.input, dict):
#                     if current_tool_use:
#                         current_tool_use["input"].update(tool_delta.input)
                        
#                         # Update the arguments in tool_calls list
#                         for i, call in enumerate(tool_calls):
#                             if call["id"] == current_tool_use["id"]:
#                                 tool_calls[i]["function"]["arguments"] = json.dumps(current_tool_use["input"])
            
#             # Handle message stop
#             if hasattr(chunk, 'type') and chunk.type == 'message_stop':
#                 if tool_use_detected and tool_calls:
#                     # If we detected tool use, return the info for execution
#                     return {
#                         "finish_reason": "tool_calls",
#                         "content": full_content,
#                         "tool_calls": tool_calls
#                     }
#                 else:
#                     # Normal completion without tool use
#                     return {
#                         "finish_reason": "stop",
#                         "content": full_content
#                     }
        
#         # Default return if stream ends unexpectedly
#         return {
#             "finish_reason": "stop",
#             "content": full_content
#         }
    
#     def execute_tool_calls(self, tool_calls, project_id):
#         """Execute tool calls and return responses"""
#         tool_responses = []
#         notifications = []
        
#         for tool_call in tool_calls:
#             tool_call_id = tool_call["id"]
#             function_name = tool_call["function"]["name"]
#             arguments_str = tool_call["function"]["arguments"]
            
#             print(f"[AnthropicProvider] Executing tool: {function_name} with arguments: {arguments_str}")
            
#             try:
#                 # Handle empty arguments string by defaulting to an empty object
#                 if not arguments_str.strip():
#                     arguments = {}
#                     print(f"[AnthropicProvider] Empty arguments string for {function_name}, defaulting to empty object")
#                 else:
#                     arguments = json.loads(arguments_str)
#                 tool_result = app_functions(function_name, arguments, project_id)
                
#                 # Format tool response
#                 if tool_result is None:
#                     response_content = "The function completed with no result."
#                 elif isinstance(tool_result, dict) and tool_result.get("is_notification") is True:
#                     # Handle notification
#                     response_content = str(tool_result.get("message_to_agent", ""))
#                     # Store notification for later yielding
#                     notifications.append({
#                         "is_notification": True,
#                         "notification_type": tool_result.get("notification_type", ""),
#                         "function_name": function_name
#                     })
#                 else:
#                     # Standard response
#                     if isinstance(tool_result, str):
#                         response_content = tool_result
#                     elif isinstance(tool_result, dict):
#                         response_content = str(tool_result.get("message_to_agent", ""))
#                     else:
#                         response_content = str(tool_result)
                
#                 print(f"[AnthropicProvider] Tool success: {function_name}. Result length: {len(response_content)}")
            
#             except json.JSONDecodeError as e:
#                 response_content = f"Error parsing tool arguments: {str(e)}"
#                 print(f"[AnthropicProvider Error] {response_content}")
#             except Exception as e:
#                 response_content = f"Error executing tool {function_name}: {str(e)}"
#                 print(f"[AnthropicProvider Error] {response_content}\n{traceback.format_exc()}")
            
#             # Add tool response
#             tool_responses.append({
#                 "role": "tool",
#                 "tool_call_id": tool_call_id,
#                 "content": response_content
#             })
        
#         return tool_responses, notifications
    
#     def generate_stream(self, messages, project_id):
#         """Generate streaming response from the AI provider with improved tool handling"""
#         current_messages = list(messages)  # Work on a copy
        
#         while True:  # Loop to handle multi-turn tool calls
#             try:
#                 print(f"[AnthropicProvider] Starting API call with {len(current_messages)} messages")
                
#                 # Convert messages to Anthropic format
#                 anthropic_messages, system_message = self.convert_messages_to_anthropic_format(current_messages)
                
#                 # Convert tools to Anthropic format
#                 anthropic_tools = self.convert_openai_to_anthropic_tools(ai_tools)
                
#                 # Prepare request parameters
#                 params = {
#                     "model": self.model,
#                     "messages": anthropic_messages,
#                     "max_tokens": 28000
#                 }
                
#                 # Add system message if present
#                 if system_message:
#                     params["system"] = system_message
                    
#                 # Add tools if available
#                 if anthropic_tools:
#                     params["tools"] = anthropic_tools
                
#                 # Make API call with streaming
#                 with self.client.messages.stream(**params) as stream:
#                     # Process stream chunks and collect results
#                     stream_processor = self.process_tool_use_stream(stream, project_id)
                    
#                     # Use a generator to process the streamed response
#                     stream_result = None
#                     for chunk_result in stream_processor:
#                         if isinstance(chunk_result, dict):
#                             # This is the final result data
#                             stream_result = chunk_result
#                         else:
#                             # This is streaming text content, pass it through
#                             yield chunk_result
                    
#                     # If we didn't get a proper result, create a default one
#                     if not stream_result:
#                         print("[AnthropicProvider Warning] No stream result received")
#                         return
                    
#                     # Check if tool calls were made
#                     if stream_result.get("finish_reason") == "tool_calls":
#                         tool_calls = stream_result.get("tool_calls", [])
#                         content = stream_result.get("content")
                        
#                         # Add assistant message with tool calls to the conversation
#                         assistant_message = {
#                             "role": "assistant",
#                             "tool_calls": tool_calls
#                         }
#                         if content:
#                             assistant_message["content"] = content
                        
#                         current_messages.append(assistant_message)
                        
#                         # Execute tools
#                         tool_responses, notifications = self.execute_tool_calls(tool_calls, project_id)
                        
#                         # Yield any notifications to the consumer
#                         for notification in notifications:
#                             print(f"[AnthropicProvider] Yielding notification: {notification}")
#                             yield json.dumps(notification)
                        
#                         # Add tool responses to the conversation
#                         current_messages.extend(tool_responses)
                        
#                         # Continue to next API call in the multi-turn conversation
#                         continue
#                     else:
#                         # Conversation complete
#                         return
                    
#             except Exception as e:
#                 error_message = f"Error with Anthropic stream: {str(e)}"
#                 print(f"[AnthropicProvider Critical Error] {error_message}\n{traceback.format_exc()}")
#                 yield error_message
#                 return


# class GoogleAIProvider(AIProvider):
#     """Google AI provider implementation"""
    
#     def __init__(self):
#         api_key = os.getenv('GEMINI_API_KEY')
#         if not api_key:
#             raise ValueError("GEMINI_API_KEY environment variable is not set. Please check your .env file.")
        
#         # Initialize the Google Generative AI client
#         # genai.configure(api_key=api_key)
#         self.client = genai.Client(api_key=api_key)
#         self.model_id = "gemini-2.5-pro-exp-03-25"  # Using Gemini 2.0 Flash as default
    
#     def generate_stream(self, messages, project_id):
#         try:
#             # Convert from OpenAI format to Google format
#             google_contents = []
#             system_message = None
            
#             # Extract system message if present
#             for m in messages:
#                 if m["role"] == "system":
#                     system_message = m["content"]
#                     break
            
#             # Convert remaining messages to Google format
#             for m in messages:
#                 if m["role"] == "system":
#                     continue
                
#                 role = "user" if m["role"] == "user" else "model"
#                 if m["role"] == "user" and system_message and not google_contents:
#                     # Add system message as a preamble to the first user message
#                     google_contents.append({
#                         "role": role,
#                         "parts": [{"text": f"{system_message}\n\n{m['content']}"}]
#                     })
#                 elif m["role"] == "assistant" and "tool_calls" in m:
#                     # Handle tool calls in the conversation history
#                     content_parts = []
#                     if m["content"]:
#                         content_parts.append({"text": m["content"]})
                    
#                     # Add function calls
#                     for tool_call in m.get("tool_calls", []):
#                         if "function" in tool_call:
#                             # Handle empty arguments by defaulting to an empty object
#                             arguments_str = tool_call["function"]["arguments"]
#                             if not arguments_str.strip():
#                                 args = {}
#                                 print(f"[GoogleAIProvider] Empty arguments string, defaulting to empty object")
#                             else:
#                                 args = json.loads(arguments_str)
                                
#                             function_call = {
#                                 "name": tool_call["function"]["name"],
#                                 "args": args
#                             }
#                             content_parts.append({"function_call": function_call})
                    
#                     google_contents.append({
#                         "role": role,
#                         "parts": content_parts
#                     })
#                 else:
#                     google_contents.append({
#                         "role": role,
#                         "parts": [{"text": m["content"]}]
#                     })
            
#             # Prepare configuration
#             config = {}

#             tools = ai_tools
            
#             # Add tools if provided
#             if tools:
#                 google_tools = []
#                 for tool in tools:
#                     if tool.get("type") == "function":
#                         function_def = tool["function"]
#                         # Convert parameters to uppercase types as required by Google API
#                         parameters = self._convert_json_schema_types(function_def.get("parameters", {}))
                        
#                         function_declaration = FunctionDeclaration(
#                             name=function_def["name"],
#                             description=function_def.get("description", ""),
#                             parameters=parameters
#                         )
#                         google_tools.append(Tool(function_declarations=[function_declaration]))
                
#                 if google_tools:
#                     config["tools"] = google_tools
            
#             # Add temperature and other generation config options
#             # config["temperature"] = 0.7
#             config["max_output_tokens"] = 1024
            
#             # Create the generation config
#             generation_config = GenerateContentConfig(**config)
            
#             # Get the model
#             # model = self.client.models.get(self.model_id)
#             client = self.client
            
#             # Generate content with streaming
#             stream = client.models.generate_content_stream(
#                 model=self.model_id,
#                 contents=google_contents,
#                 config=generation_config
#             )
            
#             # Process the streaming response
#             for chunk in stream:
#                 # Check for text responses
#                 if hasattr(chunk, 'candidates') and chunk.candidates:
#                     for candidate in chunk.candidates:
#                         if hasattr(candidate, 'content') and candidate.content:
#                             for part in candidate.content.parts:
#                                 if hasattr(part, 'text') and part.text:
#                                     yield part.text
                
#                 # Check for function calls
#                 if hasattr(chunk, 'candidates') and chunk.candidates:
#                     for candidate in chunk.candidates:
#                         if hasattr(candidate, 'function_calls') and candidate.function_calls:
#                             for function_call in candidate.function_calls:
#                                 yield json.dumps({
#                                     "tool_call": {
#                                         "name": function_call.name,
#                                         "arguments": function_call.args
#                                     }
#                                 })
        
#         except Exception as e:
#             yield f"Error with Google AI: {str(e)}"
    
#     def _convert_json_schema_types(self, schema):
#         """Convert JSON schema types to Google's format (uppercase types)"""
#         if not schema:
#             return schema
            
#         result = schema.copy()
        
#         # Use dictionary mapping instead of if-elif chains
#         type_map = {
#             "object": "OBJECT",
#             "array": "ARRAY",
#             "string": "STRING",
#             "number": "NUMBER",
#             "integer": "INTEGER",
#             "boolean": "BOOLEAN",
#             "null": "NULL"
#         }
        
#         # Convert type values to uppercase
#         if "type" in result:
#             result["type"] = type_map.get(result["type"], result["type"])
        
#         # Recursively convert nested properties
#         if "properties" in result and isinstance(result["properties"], dict):
#             for prop_name, prop_schema in result["properties"].items():
#                 result["properties"][prop_name] = self._convert_json_schema_types(prop_schema)
        
#         # Convert array item types
#         if "items" in result and isinstance(result["items"], dict):
#             result["items"] = self._convert_json_schema_types(result["items"])
        
#         return result 