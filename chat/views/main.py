import json
import openai
import os
from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse, StreamingHttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from chat.models import Conversation, Message
import markdown
from django.conf import settings
from chat.utils.ai_providers import AIProvider
from django.contrib.auth.decorators import login_required
from projects.models import Project


@login_required
def index(request):
    """Render the main chat interface."""
    context = {}
    if hasattr(request.user, 'profile'):
        context['sidebar_collapsed'] = request.user.profile.sidebar_collapsed
    return render(request, 'chat/main.html', context)

@login_required
def project_chat(request, project_id):
    """Create a new conversation linked to a project and redirect to the chat interface."""
    project = get_object_or_404(Project, id=project_id, owner=request.user)
    
    # Create a new conversation
    # conversation = Conversation.objects.create(
    #     user=request.user,
    #     title=f"Chat for {project.name}"
    # )
    
    # # Link the conversation to the project
    # project.conversations.add(conversation)
    # project.save()
    
    # Add an initial system message that mentions the project
    # Message.objects.create(
    #     conversation=conversation,
    #     role='system',
    #     content=f""
    # )
    
    # Redirect to the chat interface with this conversation open
    context = {
        # 'conversation_id': conversation.id,
        'project': project,
        'project_id': project.id
    }
    
    if hasattr(request.user, 'profile'):
        context['sidebar_collapsed'] = request.user.profile.sidebar_collapsed
        
    return render(request, 'chat/main.html', context)

@login_required
def show_conversation(request, conversation_id):
    """Show a specific conversation."""
    conversation = get_object_or_404(Conversation, id=conversation_id, user=request.user)
    
    # Check if this conversation is linked to any project
    project = None
    if hasattr(conversation, 'projects'):
        projects = conversation.projects.all()
        if projects.exists():
            project = projects.first()
    
    context = {
        'conversation_id': conversation.id
    }
    
    if project:
        context['project'] = project
        context['project_id'] = project.id
    
    if hasattr(request.user, 'profile'):
        context['sidebar_collapsed'] = request.user.profile.sidebar_collapsed
        
    return render(request, 'chat/main.html', context)


@require_http_methods(["GET"])
@login_required
def conversation_list(request, project_id):
    """Return a list of all conversations for the current user."""
    # Get base queryset for user's conversations
    conversations = Conversation.objects.filter(user=request.user)
    
    # Filter by project using the correct field name
    if project_id:
        conversations = conversations.filter(project_id=project_id)
    
    # Order by most recent first
    conversations = conversations.order_by('-updated_at')
    
    data = []
    for conv in conversations:
        # Check if this conversation has a project
        project_info = None
        if conv.project:
            project_info = {
                'id': conv.project.id,
                'name': conv.project.name,
                'icon': conv.project.icon
            }
        
        data.append({
            'id': conv.id,
            'title': conv.title or f"Conversation {conv.id}",
            'created_at': conv.created_at.isoformat(),
            'updated_at': conv.updated_at.isoformat(),
            'project': project_info
        })
    
    return JsonResponse(data, safe=False)

@require_http_methods(["GET", "DELETE"])
@login_required
def conversation_detail(request, conversation_id):
    """Return messages for a specific conversation or delete the conversation."""
    conversation = get_object_or_404(Conversation, id=conversation_id, user=request.user)
    
    # Handle DELETE request
    if request.method == "DELETE":
        conversation.delete()
        return JsonResponse({"status": "success", "message": "Conversation deleted successfully"})
    
    # Handle GET request
    messages = conversation.messages.all()
    
    # Check if this conversation is linked to any project
    project_info = None
    if hasattr(conversation, 'projects'):
        projects = conversation.projects.all()
        if projects.exists():
            project = projects.first()
            project_info = {
                'id': project.id,
                'name': project.name,
                'icon': project.icon
            }
    
    data = {
        'id': conversation.id,
        'title': conversation.title,
        'created_at': conversation.created_at.isoformat(),
        'project': project_info,
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

# @csrf_exempt
# @require_http_methods(["GET", "POST"])
# def ai_provider(request):
#     """Get or set the AI provider."""
#     if request.method == "GET":
#         return JsonResponse({"provider": settings.AI_PROVIDER_DEFAULT})
#     else:
#         data = json.loads(request.body)
#         provider = data.get('provider')
#         # In a real app, you might store this in the user's session or profile
#         # For now, we'll just return the provided value
#         return JsonResponse({"provider": provider})

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