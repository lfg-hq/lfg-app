from django.db import models
from django.utils import timezone

# Create your models here.

class DockerSandbox(models.Model):
    """
    Model to store information about Docker sandboxes for projects and conversations.
    """
    STATUS_CHOICES = (
        ('created', 'Created'),
        ('running', 'Running'),
        ('stopped', 'Stopped'),
        ('error', 'Error'),
    )
    
    project_id = models.CharField(max_length=255, blank=True, null=True, 
                                 help_text="Project identifier associated with this sandbox")
    conversation_id = models.CharField(max_length=255, blank=True, null=True,
                                      help_text="Conversation identifier associated with this sandbox")
    container_id = models.CharField(max_length=255, help_text="Docker container ID")
    container_name = models.CharField(max_length=255, help_text="Docker container name")
    image = models.CharField(max_length=255, help_text="Docker image used")
    code_dir = models.CharField(max_length=512, blank=True, null=True, 
                               help_text="Directory containing the code for this sandbox")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='created', 
                             help_text="Current status of the sandbox")
    resource_limits = models.JSONField(blank=True, null=True, 
                                      help_text="Resource limits applied to the container")
    created_at = models.DateTimeField(auto_now_add=True, help_text="When the sandbox was created")
    updated_at = models.DateTimeField(auto_now=True, help_text="When the sandbox was last updated")
    started_at = models.DateTimeField(blank=True, null=True, help_text="When the sandbox was started")
    stopped_at = models.DateTimeField(blank=True, null=True, help_text="When the sandbox was stopped")
    
    class Meta:
        indexes = [
            models.Index(fields=['project_id']),
            models.Index(fields=['conversation_id']),
            models.Index(fields=['container_id']),
            models.Index(fields=['status']),
        ]
        # Add uniqueness constraints
        constraints = [
            models.UniqueConstraint(
                fields=['project_id'], 
                condition=models.Q(conversation_id__isnull=True),
                name='unique_project_sandbox'
            ),
            models.UniqueConstraint(
                fields=['conversation_id'], 
                condition=models.Q(project_id__isnull=True),
                name='unique_conversation_sandbox'
            ),
            models.UniqueConstraint(
                fields=['project_id', 'conversation_id'],
                condition=models.Q(project_id__isnull=False, conversation_id__isnull=False),
                name='unique_project_conversation_sandbox'
            ),
        ]
        verbose_name = "Docker Sandbox"
        verbose_name_plural = "Docker Sandboxes"
    
    def __str__(self):
        return f"Sandbox {self.container_name} ({self.status})"
    
    def mark_as_running(self, container_id=None, port=None, code_dir=None):
        """Mark the sandbox as running with the given container ID and port."""
        self.status = 'running'
        self.started_at = timezone.now()
        
        if container_id:
            self.container_id = container_id
        
        if port is not None:
            self.port = port
            
        if code_dir is not None:
            self.code_dir = code_dir
            
        self.save()
    
    def mark_as_stopped(self):
        """Mark the sandbox as stopped."""
        self.status = 'stopped'
        self.stopped_at = timezone.now()
        self.save()
    
    def mark_as_error(self):
        """Mark the sandbox as having an error."""
        self.status = 'error'
        self.save()


class DockerPortMapping(models.Model):
    """
    Model to store port mappings for Docker sandboxes.
    Each Docker sandbox can have multiple port mappings.
    """
    sandbox = models.ForeignKey(
        DockerSandbox,
        on_delete=models.CASCADE,
        related_name='port_mappings',
        help_text="Docker sandbox this port mapping belongs to"
    )
    container_port = models.IntegerField(
        help_text="Port number inside the container"
    )
    host_port = models.IntegerField(
        help_text="Port number on the host machine mapped to the container port"
    )
    command = models.CharField(
        max_length=512,
        blank=True,
        null=True,
        help_text="Command associated with this port (e.g., service running on this port)"
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text="When the port mapping was created"
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        help_text="When the port mapping was last updated"
    )
    
    class Meta:
        indexes = [
            models.Index(fields=['sandbox']),
            models.Index(fields=['container_port']),
            models.Index(fields=['host_port']),
        ]
        verbose_name = "Docker Port Mapping"
        verbose_name_plural = "Docker Port Mappings"
        unique_together = [
            ('sandbox', 'container_port'),
            ('sandbox', 'host_port'),
        ]
    
    def __str__(self):
        return f"{self.host_port}:{self.container_port} for {self.sandbox.container_name}"


class KubernetesPod(models.Model):
    """
    Model to store information about Kubernetes pods for projects and conversations.
    """
    STATUS_CHOICES = (
        ('created', 'Created'),
        ('running', 'Running'),
        ('stopped', 'Stopped'),
        ('error', 'Error'),
    )
    
    project_id = models.CharField(max_length=255, blank=True, null=True, 
                                 help_text="Project identifier associated with this pod")
    conversation_id = models.CharField(max_length=255, blank=True, null=True,
                                      help_text="Conversation identifier associated with this pod")
    pod_name = models.CharField(max_length=255, help_text="Kubernetes pod name")
    namespace = models.CharField(max_length=255, help_text="Kubernetes namespace")
    image = models.CharField(max_length=255, help_text="Container image used")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='created', 
                             help_text="Current status of the pod")
    resource_limits = models.JSONField(blank=True, null=True, 
                                      help_text="Resource limits applied to the pod")
    service_details = models.JSONField(blank=True, null=True,
                                      help_text="Details of the associated services (ports, node ports, etc.)")
    ssh_connection_details = models.JSONField(blank=True, null=True,
                                            help_text="SSH connection details for the k8s host server")
    # New fields for direct Kubernetes API access
    cluster_host = models.CharField(max_length=255, blank=True, null=True,
                                  help_text="Kubernetes cluster API server host")
    kubeconfig = models.JSONField(blank=True, null=True,
                                help_text="Kubernetes config as JSON for direct API access")
    token = models.TextField(blank=True, null=True,
                           help_text="Kubernetes API token for authentication")
    created_at = models.DateTimeField(auto_now_add=True, help_text="When the pod was created")
    updated_at = models.DateTimeField(auto_now=True, help_text="When the pod was last updated")
    started_at = models.DateTimeField(blank=True, null=True, help_text="When the pod was started")
    stopped_at = models.DateTimeField(blank=True, null=True, help_text="When the pod was stopped")
    
    class Meta:
        indexes = [
            models.Index(fields=['project_id']),
            models.Index(fields=['conversation_id']),
            models.Index(fields=['pod_name']),
            models.Index(fields=['namespace']),
            models.Index(fields=['status']),
        ]
        # Add uniqueness constraints
        constraints = [
            models.UniqueConstraint(
                fields=['project_id'], 
                condition=models.Q(conversation_id__isnull=True),
                name='unique_project_pod'
            ),
            models.UniqueConstraint(
                fields=['conversation_id'], 
                condition=models.Q(project_id__isnull=True),
                name='unique_conversation_pod'
            ),
            models.UniqueConstraint(
                fields=['project_id', 'conversation_id'],
                condition=models.Q(project_id__isnull=False, conversation_id__isnull=False),
                name='unique_project_conversation_pod'
            ),
        ]
        verbose_name = "Kubernetes Pod"
        verbose_name_plural = "Kubernetes Pods"
    
    def __str__(self):
        return f"Pod {self.pod_name} in {self.namespace} ({self.status})"
    
    def mark_as_running(self, pod_name=None, service_details=None):
        """Mark the pod as running with the given details."""
        self.status = 'running'
        self.started_at = timezone.now()
        
        if pod_name:
            self.pod_name = pod_name
            
        if service_details is not None:
            self.service_details = service_details
            
        self.save()
    
    def mark_as_stopped(self):
        """Mark the pod as stopped."""
        self.status = 'stopped'
        self.stopped_at = timezone.now()
        self.save()
    
    def mark_as_error(self):
        """Mark the pod as having an error."""
        self.status = 'error'
        self.save()
