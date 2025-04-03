import json
import asyncio
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.conf import settings

# Import everything we need at the module level
# These imports are safe now because django.setup() is called in asgi.py before imports
from django.contrib.auth.models import User
from chat.models import Conversation, Message
from chat.utils.ai_providers import AIProvider


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
                provider_name = text_data_json.get('provider', settings.AI_PROVIDER_DEFAULT)
                
                # Get or create conversation
                if conversation_id and not self.conversation:
                    self.conversation = await self.get_conversation(conversation_id)
                
                if not self.conversation:
                    self.conversation = await self.create_conversation(user_message[:50])
                
                # Save user message
                await self.save_message('user', user_message)
                
                # Reset stop flag
                self.should_stop_generation = False
                
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
        await self.send(text_data=json.dumps({
            'type': 'ai_chunk',
            'chunk': event['chunk'],
            'is_final': event['is_final'],
            'conversation_id': event.get('conversation_id'),
            'provider': event.get('provider'),
            'project_id': event.get('project_id')
        }))
    
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
                "content": await self.get_system_prompt()
            })
        
        # Get the appropriate AI provider
        provider = AIProvider.get_provider(provider_name)
        
        try:
            # Generate streaming response
            full_response = ""
            
            # Process the stream in an async context
            async for content in self.process_ai_stream(provider, messages):
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
                await self.update_conversation_title(user_message[:50])
            
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
    
    async def process_ai_stream(self, provider, messages):
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
                for content in provider.generate_stream(messages):
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
                
                yield chunk
                
                # After yielding a chunk, check again if we should stop
                # This ensures we stop as soon as possible after a user request
                if self.should_stop_generation:
                    print("Stopping AI stream generation after yielding chunk")
                    break
                
        except Exception as e:
            print(f"Error in process_ai_stream: {str(e)}")
            yield f"Error generating response: {str(e)}"
    
    async def get_system_prompt(self):
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
    def create_conversation(self, title):
        """
        Create a new conversation
        """
        return Conversation.objects.create(
            user=self.user,
            title=title
        )
    
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
            
        messages = Message.objects.filter(conversation=self.conversation).order_by('created_at')
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
        project_id = None
        if self.conversation and hasattr(self.conversation, 'projects'):
            projects = self.conversation.projects.all()
            if projects.exists():
                project_id = projects.first().id
        return project_id 