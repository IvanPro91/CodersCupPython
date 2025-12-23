from django.urls import path

from code_cup import code_websocket

websocket_urlpatterns = [
    path("ws/code_cup/<str:room_name>/", code_websocket.CodeCupWebSocket.as_asgi()),
]
