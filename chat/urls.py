from django.urls import path
from . import views

urlpatterns = [
    path('chat/', views.index, name='index'),
    path('chat/project/<int:project_id>/', views.project_chat, name='create_conversation'),
    path('chat/conversation/<int:conversation_id>/', views.show_conversation, name='conversation_detail'),
    path('api/projects/<int:project_id>/conversations/', views.conversation_list, name='conversation_list'),
    path('api/conversations/<int:conversation_id>/', views.conversation_detail, name='conversation_detail_api'),
    # path('api/provider/', views.ai_provider, name='ai_provider'),
    path('api/toggle-sidebar/', views.toggle_sidebar, name='toggle_sidebar'),
    # Note: The chat API endpoint (/api/chat/) has been removed
    # as it's now handled by the WebSocket consumer in chat/consumers.py
] 