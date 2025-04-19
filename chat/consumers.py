import json
import asyncio
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.conf import settings

# Import everything we need at the module level
# These imports are safe now because django.setup() is called in asgi.py before imports
from django.contrib.auth.models import User
from chat.models import Conversation, Message
from chat.utils import AIProvider, get_system_prompt

class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        """
        Handle WebSocket connection
        """
        try:
            # Get user from scope
            self.user = self.scope["user"]
            
            # Each user joins their own room based on their username
            if self.user.is_authenticated:
                self.room_name = f"chat_{self.user.username}"
            else:
                self.room_name = "chat_anonymous"
                print("Warning: User is not authenticated, using anonymous chat room")
            
            # Create a sanitized group name for the channel layer
            self.room_group_name = self.room_name.replace(" ", "_")
            
            # Accept connection
            await self.accept()
            print(f"WebSocket connection accepted for user {self.user} in room {self.room_group_name}")
            
            # Initialize properties
            self.conversation = None
            self.active_generation_task = None
            self.should_stop_generation = False
            
            try:
                # Join room group
                await self.channel_layer.group_add(
                    self.room_group_name,
                    self.channel_name
                )
                print(f"User {self.user} added to group {self.room_group_name}")
                self.using_groups = True
            except Exception as group_error:
                print(f"Error adding to channel group: {str(group_error)}")
                self.using_groups = False
            
            # Load chat history if conversation_id is provided in query string
            query_string = self.scope.get('query_string', b'').decode()
            query_params = dict(param.split('=') for param in query_string.split('&') if '=' in param)
            conversation_id = query_params.get('conversation_id')
            
            if conversation_id:
                # Get existing conversation
                self.conversation = await self.get_conversation(conversation_id)
                
                # Send chat history to client
                if self.conversation:
                    messages = await self.get_chat_history()
                    await self.send(text_data=json.dumps({
                        'type': 'chat_history',
                        'messages': messages
                    }))
            
        except Exception as e:
            print(f"Error in WebSocket connect: {str(e)}")
            # Try to accept and send error
            try:
                await self.accept()
                await self.send(text_data=json.dumps({
                    'type': 'error',
                    'message': f"Connection error: {str(e)}"
                }))
            except Exception as inner_e:
                print(f"Could not accept WebSocket connection: {str(inner_e)}")
    
    async def disconnect(self, close_code):
        """
        Handle WebSocket disconnection
        """
        try:
            if hasattr(self, 'using_groups') and self.using_groups:
                await self.channel_layer.group_discard(
                    self.room_group_name,
                    self.channel_name
                )
                print(f"User {self.user} removed from group {self.room_group_name}")
        except Exception as e:
            print(f"Error during disconnect: {str(e)}")
    
    async def receive(self, text_data):
        """
        Receive message from WebSocket
        """
        try:
            text_data_json = json.loads(text_data)
            message_type = text_data_json.get('type', 'message')
            
            if message_type == 'message':
                user_message = text_data_json.get('message', '')
                conversation_id = text_data_json.get('conversation_id')
                project_id = text_data_json.get('project_id')
                
                # Get or create conversation
                if conversation_id and not self.conversation:
                    self.conversation = await self.get_conversation(conversation_id)
                
                if not self.conversation:
                    # Require a project_id to create a conversation
                    if not project_id:
                        await self.send_error("A project ID is required to create a conversation")
                        return
                    
                    self.conversation = await self.create_conversation(user_message[:50], project_id)
                    
                    # Check if conversation was created
                    if not self.conversation:
                        await self.send_error("Failed to create conversation. Please check your project ID.")
                        return
                
                # Save user message
                await self.save_message('user', user_message)
                
                # Reset stop flag
                self.should_stop_generation = False
                
                provider_name = settings.AI_PROVIDER_DEFAULT
                # Generate AI response in background task
                # Store the task so we can cancel it if needed
                self.active_generation_task = asyncio.create_task(
                    self.generate_ai_response(user_message, provider_name, project_id)
                )
            
            elif message_type == 'stop_generation':
                # Handle stop generation request
                conversation_id = text_data_json.get('conversation_id')
                
                # Set flag to stop generation
                self.should_stop_generation = True
                
                # Cancel the active task if it exists
                if self.active_generation_task and not self.active_generation_task.done():
                    print(f"Canceling active generation task for conversation {conversation_id}")
                    # We don't actually cancel the task as it may be in the middle of stream processing
                    # Instead, we set a flag that will be checked during stream processing
                
                # Save an indicator that generation was stopped
                if self.conversation:
                    await self.save_message('system', '*Generation stopped by user*')
                
                # Send stop confirmation to client
                await self.send(text_data=json.dumps({
                    'type': 'stop_confirmed'
                }))
                
                # Log stop request
                print(f"Stop generation requested for conversation {conversation_id}")
            
        except Exception as e:
            print(f"Error processing received message: {str(e)}")
            await self.send_error(f"Error processing message: {str(e)}")
    
    async def chat_message(self, event):
        """
        Send message to WebSocket
        """
        await self.send(text_data=json.dumps({
            'type': 'message',
            'message': event['message'],
            'sender': event['sender']
        }))
    
    async def ai_response_chunk(self, event):
        """
        Send AI response chunk to WebSocket
        """
        # Create response data with all available properties
        response_data = {
            'type': 'ai_chunk',
            'chunk': event['chunk'],
            'is_final': event['is_final'],
            'conversation_id': event.get('conversation_id'),
            'provider': event.get('provider'),
            'project_id': event.get('project_id')
        }
        
        # Add notification data if present
        if event.get('is_notification'):
            print("\n\n=== NOTIFICATION BEING SENT TO CLIENT ===")
            print(f"Notification type: {event.get('notification_type', 'features')}")
            print(f"Is early notification: {event.get('early_notification', False)}")
            print(f"Function name: {event.get('function_name', '')}")
            print(f"Full event data: {event}")
            print("=======================================\n\n")
            
            response_data['is_notification'] = True
            response_data['notification_type'] = event.get('notification_type', 'features')
            
            # Add early notification flag and function name if present
            if event.get('early_notification'):
                response_data['early_notification'] = True
                response_data['function_name'] = event.get('function_name', '')
        
        await self.send(text_data=json.dumps(response_data))
    
    async def generate_ai_response(self, user_message, provider_name, project_id=None):
        """
        Generate response from AI
        """
        # Send typing indicator
        try:
            if hasattr(self, 'using_groups') and self.using_groups:
                await self.channel_layer.group_send(
                    self.room_group_name,
                    {
                        'type': 'ai_response_chunk',
                        'chunk': '',
                        'is_final': False
                    }
                )
            else:
                await self.send(text_data=json.dumps({
                    'type': 'ai_chunk',
                    'chunk': '',
                    'is_final': False
                }))
        except Exception as e:
            print(f"Error sending typing indicator: {str(e)}")
        
        # Get conversation history
        messages = await self.get_messages_for_ai()
        
        # Add system message if not present
        if not any(msg["role"] == "system" for msg in messages):
            messages.insert(0, {
                "role": "system",
                "content": await get_system_prompt()
            })
        
        # Get the appropriate AI provider
        provider = AIProvider.get_provider(provider_name)
        
        try:
            # Generate streaming response
            full_response = ""
            
            # Process the stream in an async context
            async for content in self.process_ai_stream(provider, messages, project_id):
                # Check if generation should stop
                if self.should_stop_generation:
                    # Add a note to the response that generation was stopped
                    stop_message = "\n\n*Generation stopped by user*"
                    
                    # Send the stop message as the final chunk
                    try:
                        if hasattr(self, 'using_groups') and self.using_groups:
                            await self.channel_layer.group_send(
                                self.room_group_name,
                                {
                                    'type': 'ai_response_chunk',
                                    'chunk': stop_message,
                                    'is_final': False
                                }
                            )
                        else:
                            await self.send(text_data=json.dumps({
                                'type': 'ai_chunk',
                                'chunk': stop_message,
                                'is_final': False
                            }))
                    except Exception as e:
                        print(f"Error sending stop message chunk: {str(e)}")
                    
                    # Add the stop message to the full response
                    full_response += stop_message
                    
                    # Break out of the loop
                    break
                
                full_response += content
                
                # Send each chunk to the client
                try:
                    if hasattr(self, 'using_groups') and self.using_groups:
                        await self.channel_layer.group_send(
                            self.room_group_name,
                            {
                                'type': 'ai_response_chunk',
                                'chunk': content,
                                'is_final': False
                            }
                        )
                    else:
                        await self.send(text_data=json.dumps({
                            'type': 'ai_chunk',
                            'chunk': content,
                            'is_final': False
                        }))
                except Exception as e:
                    print(f"Error sending AI chunk: {str(e)}")
                
                # Small delay to simulate natural typing
                await asyncio.sleep(0.03)
            
            # Save the complete message
            await self.save_message('assistant', full_response)
            
            # Update conversation title if it's new
            if self.conversation and (not self.conversation.title or self.conversation.title == str(self.conversation.id)):
                # Use AI to generate a title based on first messages
                await self.generate_title_with_ai(user_message, full_response)
            
            # Get project_id if conversation is linked to a project
            if not project_id and self.conversation:
                project_id = await self.get_project_id()
                
            # Send message complete signal
            try:
                # Only send the final message if generation wasn't stopped
                # This prevents empty messages from being created after stopping
                if not self.should_stop_generation:
                    if hasattr(self, 'using_groups') and self.using_groups:
                        await self.channel_layer.group_send(
                            self.room_group_name,
                            {
                                'type': 'ai_response_chunk',
                                'chunk': '',
                                'is_final': True,
                                'conversation_id': self.conversation.id if self.conversation else None,
                                'provider': provider_name,
                                'project_id': project_id
                            }
                        )
                    else:
                        await self.send(text_data=json.dumps({
                            'type': 'ai_chunk',
                            'chunk': '',
                            'is_final': True,
                            'conversation_id': self.conversation.id if self.conversation else None,
                            'provider': provider_name,
                            'project_id': project_id
                        }))
                else:
                    # For stopped generation, just send conversation metadata without creating a new message
                    if hasattr(self, 'using_groups') and self.using_groups:
                        await self.channel_layer.group_send(
                            self.room_group_name,
                            {
                                'type': 'ai_response_chunk',
                                'chunk': None,  # Using None instead of empty string to distinguish
                                'is_final': True,
                                'conversation_id': self.conversation.id if self.conversation else None,
                                'provider': provider_name,
                                'project_id': project_id
                            }
                        )
                    else:
                        await self.send(text_data=json.dumps({
                            'type': 'ai_chunk',
                            'chunk': None,  # Using None instead of empty string to distinguish
                            'is_final': True,
                            'conversation_id': self.conversation.id if self.conversation else None,
                            'provider': provider_name,
                            'project_id': project_id
                        }))
            except Exception as e:
                print(f"Error sending completion signal: {str(e)}")
            
            # Clear the active task reference
            self.active_generation_task = None
            
        except Exception as e:
            error_message = f"Sorry, I encountered an error: {str(e)}"
            await self.save_message('assistant', error_message)
            
            try:
                if hasattr(self, 'using_groups') and self.using_groups:
                    await self.channel_layer.group_send(
                        self.room_group_name,
                        {
                            'type': 'chat_message',
                            'message': error_message,
                            'sender': 'assistant'
                        }
                    )
                else:
                    await self.send(text_data=json.dumps({
                        'type': 'message',
                        'message': error_message,
                        'sender': 'assistant'
                    }))
            except Exception as inner_e:
                print(f"Error sending error message: {str(inner_e)}")
                await self.send_error(error_message)
            
            # Clear the active task reference
            self.active_generation_task = None
    
    async def process_ai_stream(self, provider, messages, project_id):
        """
        Process the AI provider's stream in an async-friendly way
        
        This method wraps the synchronous generate_stream method of the AI provider
        in an asynchronous context by running it in a thread pool executor.
        """
        try:
            # Get the event loop
            loop = asyncio.get_running_loop()
            
            # Create a function that will process each item from the generator
            def process_stream():
                result = []
                # We'll capture all chunks in one go, as the actual AI providers may not
                # support cancellation mid-stream
                for content in provider.generate_stream(messages, project_id):
                    result.append(content)
                    # We yield by appending to a result list, then returning it
                    # This approach avoids having to convert a generator to an async generator
                return result
            
            # Run the synchronous generator in a thread pool and get all chunks
            chunks = await loop.run_in_executor(None, process_stream)
            
            # Yield each chunk with a small delay to simulate typing
            # This is where we can check the should_stop_generation flag
            for chunk in chunks:
                # Check if we should stop generation before yielding the next chunk
                if self.should_stop_generation:
                    print("Stopping AI stream generation due to user request")
                    # We break here to stop yielding chunks, but the generation itself
                    # has already completed in the background - this is just stopping
                    # the delivery of chunks to the client
                    break
                
                # Check if this is a notification JSON
                if isinstance(chunk, str) and chunk.startswith('{') and chunk.endswith('}'):
                    try:
                        print("\n\n=== POTENTIAL NOTIFICATION JSON DETECTED ===")
                        print(f"Raw chunk: {chunk}")
                        
                        notification_data = json.loads(chunk)
                        print(f"Parsed JSON: {notification_data}")
                        
                        if 'is_notification' in notification_data and notification_data['is_notification']:
                            print("This IS a valid notification!")
                            print(f"Notification type: {notification_data.get('notification_type', 'features')}")
                            
                            # Check if this is an early notification
                            is_early = notification_data.get('early_notification', False)
                            function_name = notification_data.get('function_name', '')
                            print(f"Is early notification__ 11: {is_early}")
                            print(f"Function name for early notification: {function_name}")
                            print("=======================================\n\n")
                            
                            # This is a notification - send it as a special message
                            notification_message = {
                                'type': 'ai_chunk',
                                'chunk': '',  # No visible content
                                'is_final': False,
                                'is_notification': True,
                                'notification_type': notification_data.get('notification_type', 'features')
                            }
                            
                            # Add early notification flag and function name if present
                            if is_early:
                                notification_message['early_notification'] = True
                                notification_message['function_name'] = function_name
                            
                            if hasattr(self, 'using_groups') and self.using_groups:
                                await self.channel_layer.group_send(
                                    self.room_group_name,
                                    {
                                        'type': 'ai_response_chunk',
                                        **notification_message
                                    }
                                )
                            else:
                                await self.send(text_data=json.dumps(notification_message))
                            continue  # Skip yielding this chunk as text
                        else:
                            print("This is NOT a notification (missing is_notification flag)")
                            print("=======================================\n\n")
                    except json.JSONDecodeError:
                        print("Not a valid JSON - treating as normal text")
                        print("=======================================\n\n")
                        # Not a valid JSON notification, treat as normal text
                        pass
                
                # Normal text chunk
                yield chunk
                
                # After yielding a chunk, check again if we should stop
                # This ensures we stop as soon as possible after a user request
                if self.should_stop_generation:
                    print("Stopping AI stream generation after yielding chunk")
                    break
                
        except Exception as e:
            print(f"Error in process_ai_stream: {str(e)}")
            yield f"Error generating response: {str(e)}"
    
    async def get_system_prompt_(self):
        """
        Get the system prompt for the AI
        """
        return """
You are an expert technical product manager. You will respond in markdown format. You will greet the user
saying that you are michael scott.

You will offer your help in helping the client build useful web apps and other software. 

You will also offer to help the client with their projects.

When they provide a requirement, and if it is not clear or absurd, you will ask for clarification..

You will ask questions as many times as required. 

Then when you have enough information, you will create a rough PRD of the project and share it 
with the client. You will ask for clarification and only proceed after that.

In the PRD, you will primarily work towards defining the features, the personas who might use the app,
the core functionalities, the design layout, etc.
"""
    
    async def send_error(self, error_message):
        """
        Send error message to WebSocket
        """
        try:
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': error_message
            }))
        except Exception as e:
            print(f"Error sending error message to client: {str(e)}")
    
    @database_sync_to_async
    def get_conversation(self, conversation_id):
        """
        Get conversation by ID
        """
        try:
            return Conversation.objects.get(id=conversation_id, user=self.user)
        except Conversation.DoesNotExist:
            return None
    
    @database_sync_to_async
    def create_conversation(self, title, project_id=None):
        """
        Create a new conversation
        """
        # Only create conversation if project_id is provided
        if not project_id:
            print("Cannot create conversation without project_id")
            return None
            
        conversation = Conversation.objects.create(
            user=self.user,
            title=title
        )
        
        # Set project reference if provided
        try:
            from projects.models import Project
            project = Project.objects.get(id=project_id, owner=self.user)
            conversation.project = project
            conversation.save()
            print(f"Set project reference for conversation {conversation.id} to project {project_id}")
        except Exception as e:
            # If we can't find the project, delete the conversation we just created
            conversation.delete()
            print(f"Error setting project reference: {str(e)}")
            return None
                
        return conversation
    
    @database_sync_to_async
    def update_conversation_title(self, title):
        """
        Update the conversation title
        """
        if self.conversation:
            self.conversation.title = title
            self.conversation.save()
    
    @database_sync_to_async
    def save_message(self, role, content):
        """
        Save message to database
        """
        if self.conversation:
            return Message.objects.create(
                conversation=self.conversation,
                role=role,
                content=content
            )
        return None
    
    @database_sync_to_async
    def get_messages_for_ai(self):
        """
        Get messages for AI processing
        """
        if not self.conversation:
            return []
            
        messages = Message.objects.filter(conversation=self.conversation).order_by('-created_at')[:5]
        messages = reversed(list(messages))  # Convert to list and reverse
        print("\n\n Messages: ", messages)
        return [
            {"role": msg.role, "content": msg.content}
            for msg in messages
        ]
    
    @database_sync_to_async
    def get_chat_history(self):
        """
        Get chat history for the current conversation
        """
        if not self.conversation:
            return []
            
        messages = Message.objects.filter(conversation=self.conversation).order_by('created_at')
        return [
            {
                'role': msg.role,
                'content': msg.content,
                'timestamp': msg.created_at.isoformat()
            } for msg in messages
        ]
    
    @database_sync_to_async
    def get_project_id(self):
        """
        Get project ID if conversation is linked to a project
        """
        if self.conversation and self.conversation.project:
            return self.conversation.project.id
        return None
    
    async def generate_title_with_ai(self, user_message, ai_response):
        """
        Generate a conversation title using AI based on the first user message and AI response
        """
        # Use the same provider as the chat
        provider_name = settings.AI_PROVIDER_DEFAULT
        provider = AIProvider.get_provider(provider_name)
        
        # Create a special prompt for title generation
        title_prompt = [
            {
                "role": "system",
                "content": "Generate a short, concise title (maximum 50 characters) that summarizes this conversation. The title should capture the main topic or purpose of the discussion. Only respond with the title text, no additional commentary or formatting."
            },
            {
                "role": "user", 
                "content": f"User: {user_message[:200]}...\nAI: {ai_response[:200]}..."
            }
        ]
        
        try:
            # Generate title non-streaming
            title = ""
            async for content in self.process_ai_stream(provider, title_prompt):
                title += content
                
            # Clean and truncate the generated title
            title = title.strip()
            if len(title) > 50:
                title = title[:47] + "..."
                
            # Update the conversation title
            await self.update_conversation_title(title)
            print(f"Generated title for conversation {self.conversation.id}: {title}")
            
        except Exception as e:
            print(f"Error generating title: {str(e)}")
            # Fallback to original behavior
            await self.update_conversation_title(user_message[:50]) 