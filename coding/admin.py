from django.contrib import admin
from .models import DockerSandbox, DockerPortMapping

# Register your models here.
admin.site.register(DockerSandbox)
admin.site.register(DockerPortMapping)
