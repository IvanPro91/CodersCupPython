import os
import django
import jwt
import socketio
from channels.routing import ProtocolTypeRouter
from django.contrib.auth import get_user_model
from django.core.asgi import get_asgi_application
from config import settings

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

sio = socketio.AsyncServer(async_mode='asgi', cors_allowed_origins='*')
socketio_app = socketio.ASGIApp(sio)

User = get_user_model()

# Функция для регистрации обработчиков
def register_socketio_handlers():
    """Регистрируем базовые обработчики"""

    @sio.event
    async def connect(sid, environ, auth):
        token = auth.get("token") if auth else None
        if not token:
            return False
        try:
            jwt_config = getattr(settings, 'SIMPLE_JWT', {})
            algorithm = jwt_config.get('ALGORITHM', 'HS256')
            signing_key = jwt_config.get('SIGNING_KEY', settings.SECRET_KEY)
            user_id_claim = jwt_config.get('USER_ID_CLAIM', 'user_id')

            payload = jwt.decode(
                token,
                signing_key,
                algorithms=[algorithm]
            )
            uid = payload.get(user_id_claim)
            user = await User.objects.aget(id=uid)

            await sio.save_session(sid, {'user_id': user.id, 'username': user.username})
            await sio.emit('connected', {'message': 'Connected successfully', 'sid': sid}, room=sid)
            print("Подключен -> ", {'user_id': user.id, 'username': user.username})
        except (jwt.ExpiredSignatureError, jwt.DecodeError, User.DoesNotExist):
            print("Ошибка авторизации токена")
            return False

    @sio.event
    async def disconnect(sid):
        print(f'Socket.IO отключен: {sid}')

    from code_cup.code_websocket import register_handlers
    register_handlers(sio)


register_socketio_handlers()


application = ProtocolTypeRouter({
    "http": get_asgi_application(),
    "websocket": socketio_app,
})