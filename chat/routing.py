from django.urls import re_path

# Direct import with as_asgi() - this works because our asgi.py calls django.setup() before imports
from chat.consumers import ChatConsumer
from chat.terminal_consumer import TerminalConsumer

websocket_urlpatterns = [
    re_path(r'ws/chat/$', ChatConsumer.as_asgi()),
    re_path(r'ws/terminal/$', TerminalConsumer.as_asgi()),
] 