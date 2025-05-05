from django.db import models
from django.contrib.auth.models import User
import os
import uuid

class Conversation(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='conversations', null=True, blank=True)
    title = models.CharField(max_length=255, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    project = models.ForeignKey('projects.Project', on_delete=models.SET_NULL, related_name='direct_conversations', null=True, blank=True)
    
    def __str__(self):
        return self.title or f"Conversation {self.id}"

class Message(models.Model):
    ROLE_CHOICES = [
        ('user', 'User'),
        ('assistant', 'Assistant'),
        ('system', 'System'),
    ]
    
    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name='messages')
    role = models.CharField(max_length=10, choices=ROLE_CHOICES)
    content = models.TextField()
    content_if_file = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['created_at']
    
    def __str__(self):
        return f"{self.role}: {self.content[:50]}..."

def get_file_upload_path(instance, filename):
    """Generate a unique file path for uploaded files"""
    ext = filename.split('.')[-1]
    filename = f"{uuid.uuid4()}.{ext}"
    return os.path.join('file_storage', str(instance.conversation.id), filename)

class ChatFile(models.Model):
    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name='files')
    message = models.ForeignKey(Message, on_delete=models.CASCADE, related_name='files', null=True, blank=True)
    file = models.FileField(upload_to=get_file_upload_path)
    original_filename = models.CharField(max_length=255)
    file_type = models.CharField(max_length=100, blank=True)
    file_size = models.IntegerField(default=0)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"File: {self.original_filename} ({self.conversation})" 