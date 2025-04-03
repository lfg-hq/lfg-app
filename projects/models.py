from django.db import models
from django.contrib.auth.models import User
from django.urls import reverse
from chat.models import Conversation

# Create your models here.
class Project(models.Model):
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name="projects")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    status = models.CharField(max_length=20, choices=(
        ('active', 'Active'),
        ('archived', 'Archived'),
        ('completed', 'Completed')
    ), default='active')
    icon = models.CharField(max_length=50, default='📋')  # Default icon is a clipboard
    conversations = models.ManyToManyField(Conversation, related_name='projects', blank=True)
    
    def __str__(self):
        return self.name
    
    def get_absolute_url(self):
        return reverse('project_detail', kwargs={'project_id': self.id})
        
    def get_chat_url(self):
        """Get URL for the latest conversation or create a new one"""
        latest_conversation = self.conversations.order_by('-updated_at').first()
        if latest_conversation:
            return reverse('conversation_detail', kwargs={'conversation_id': latest_conversation.id})
        return reverse('create_conversation', kwargs={'project_id': self.id})
