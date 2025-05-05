from django.urls import re_path
from . import views_terminal

websocket_urlpatterns = [
    re_path(r'^coding/k8s/terminal/$', views_terminal.TerminalConsumer.as_asgi()),
]