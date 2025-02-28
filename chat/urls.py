from django.urls import path
from . import views

urlpatterns = [
    path('chat/', views.index, name='index'),
    path('api/chat/', views.chat_api, name='chat_api'),
    path('api/conversations/', views.conversation_list, name='conversation_list'),
    path('api/conversations/<int:conversation_id>/', views.conversation_detail, name='conversation_detail'),
    path('api/provider/', views.ai_provider, name='ai_provider'),
    path('', views.landing_page, name='landing_page'),
    path('api/toggle-sidebar/', views.toggle_sidebar, name='toggle_sidebar'),
] 