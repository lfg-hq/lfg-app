import json
import openai
import os
from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse, StreamingHttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from .models import Conversation, Message
import markdown
from django.conf import settings
from .ai_providers import AIProvider
from django.contrib.auth.decorators import login_required

# Set your OpenAI API key
# openai.api_key = os.getenv('OPENAI_API_KEY')

# Add this near the top of the file, after imports
print("DEBUG - Environment variables:")
print(f"OPENAI_API_KEY exists: {'Yes' if os.getenv('OPENAI_API_KEY') else 'No'}")
print(f"ANTHROPIC_API_KEY exists: {'Yes' if os.getenv('ANTHROPIC_API_KEY') else 'No'}")
print(f"GEMINI_API_KEY exists: {'Yes' if os.getenv('GEMINI_API_KEY') else 'No'}")

@login_required
def index(request):
    """Render the main chat interface."""
    context = {}
    if hasattr(request.user, 'profile'):
        context['sidebar_collapsed'] = request.user.profile.sidebar_collapsed
    return render(request, 'chat/index.html', context)

@csrf_exempt
@require_http_methods(["POST"])
@login_required
def chat_api(request):
    """Handle chat API requests and stream responses."""
    data = json.loads(request.body)
    user_message = data.get('message', '')
    conversation_id = data.get('conversation_id')
    provider_name = data.get('provider', settings.AI_PROVIDER_DEFAULT)
    
    # Get or create conversation
    if conversation_id:
        conversation = get_object_or_404(Conversation, id=conversation_id, user=request.user)
    else:
        conversation = Conversation.objects.create(
            user=request.user,
            title=user_message[:50]
        )
    
    # Save user message
    Message.objects.create(
        conversation=conversation,
        role='user',
        content=user_message
    )
    
    # Get conversation history
    messages = [
        {"role": msg.role, "content": msg.content}
        for msg in conversation.messages.all()
    ]
    
    # Add system message if not present
    if not any(msg["role"] == "system" for msg in messages):
        messages.insert(0, {
            "role": "system",
            "content": "You are a helpful assistant that responds with markdown formatting."
        })
    
    # Get the appropriate AI provider
    ai_provider = AIProvider.get_provider(provider_name)
    
    def generate_response():
        full_response = ""
        
        # Use the selected AI provider to generate a response
        try:
            for content in ai_provider.generate_stream(messages):
                full_response += content
                yield f"data: {json.dumps({'content': content, 'done': False})}\n\n"
        except Exception as e:
            error_message = f"Error: {str(e)}"
            yield f"data: {json.dumps({'content': error_message, 'done': False})}\n\n"
            full_response += error_message
        
        # Save assistant message
        Message.objects.create(
            conversation=conversation,
            role='assistant',
            content=full_response
        )
        
        # Update conversation title if it's new
        if not conversation.title or conversation.title == conversation.id:
            conversation.title = user_message[:50]
            conversation.save()
            
        yield f"data: {json.dumps({'content': '', 'done': True, 'conversation_id': conversation.id, 'provider': provider_name})}\n\n"
    
    return StreamingHttpResponse(
        generate_response(),
        content_type='text/event-stream'
    )

@require_http_methods(["GET"])
@login_required
def conversation_list(request):
    """Return a list of all conversations for the current user."""
    conversations = Conversation.objects.filter(user=request.user).order_by('-updated_at')
    data = [
        {
            'id': conv.id,
            'title': conv.title or f"Conversation {conv.id}",
            'created_at': conv.created_at.isoformat(),
            'updated_at': conv.updated_at.isoformat(),
        }
        for conv in conversations
    ]
    return JsonResponse(data, safe=False)

@require_http_methods(["GET"])
def conversation_detail(request, conversation_id):
    """Return messages for a specific conversation."""
    conversation = get_object_or_404(Conversation, id=conversation_id)
    messages = conversation.messages.all()
    data = {
        'id': conversation.id,
        'title': conversation.title,
        'created_at': conversation.created_at.isoformat(),
        'messages': [
            {
                'id': msg.id,
                'role': msg.role,
                'content': msg.content,
                'created_at': msg.created_at.isoformat(),
            }
            for msg in messages
        ]
    }
    return JsonResponse(data)

@csrf_exempt
@require_http_methods(["GET", "POST"])
def ai_provider(request):
    """Get or set the AI provider."""
    if request.method == "GET":
        return JsonResponse({"provider": settings.AI_PROVIDER_DEFAULT})
    else:
        data = json.loads(request.body)
        provider = data.get('provider')
        # In a real app, you might store this in the user's session or profile
        # For now, we'll just return the provided value
        return JsonResponse({"provider": provider})

def landing_page(request):
    """Render the marketing landing page."""
    return render(request, 'marketing/landing.html')

@csrf_exempt
@require_http_methods(["POST"])
@login_required
def toggle_sidebar(request):
    """Toggle sidebar collapsed state and save to user profile."""
    data = json.loads(request.body)
    collapsed = data.get('collapsed', False)
    
    # Update user profile
    if hasattr(request.user, 'profile'):
        request.user.profile.sidebar_collapsed = collapsed
        request.user.profile.save()
    
    return JsonResponse({"success": True, "collapsed": collapsed}) 