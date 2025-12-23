import os
import sys

import django
import eventlet
import socketio
from django.core.wsgi import get_wsgi_application

from config.settings import DEBUG

# Добавляем путь к проекту
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

# Инициализируем Django
django.setup()

# Получаем Django приложение
django_app = get_wsgi_application()

# Создаем Socket.IO сервер
sio = socketio.Server(
    cors_allowed_origins="*", async_mode="eventlet", logger=True, engineio_logger=True
)

# Объединяем Socket.IO с Django приложением
app = socketio.WSGIApp(sio, django_app)

# Хранилище данных
active_sessions = {}
connected_users = {}
user_sessions = {}


# События подключения/отключения
@sio.event
def connect(sid, environ):
    """Обработчик подключения клиента"""
    print(f"[Socket.IO] Клиент подключен: {sid}")
    connected_users[sid] = {
        "sid": sid,
        "connected_at": eventlet.format_isotime(eventlet.time.time()),
        "environ": environ.get("REMOTE_ADDR", "unknown"),
    }

    # Отправляем подтверждение подключения
    sio.emit("connected", {"message": "Успешное подключение к серверу"}, room=sid)


@sio.event
def disconnect(sid):
    """Обработчик отключения клиента"""
    print(f"[Socket.IO] Клиент отключен: {sid}")

    # Удаляем пользователя из хранилища
    if sid in connected_users:
        user_data = connected_users.pop(sid)

        # Уведомляем все сессии об отключении пользователя
        username = user_data.get("username")
        if username:
            for session_id, session in active_sessions.items():
                # Удаляем пользователя из сессии
                session["participants"] = [
                    p for p in session.get("participants", []) if p.get("sid") != sid
                ]

                # Уведомляем других участников
                for participant in session.get("participants", []):
                    if participant.get("sid") != sid:
                        try:
                            sio.emit(
                                "user_disconnected",
                                {
                                    "username": username,
                                    "socketId": sid,
                                    "sessionId": session_id,
                                },
                                room=participant["sid"],
                            )
                        except Exception as err:
                            print(err)
                            pass


# Пользовательские события
@sio.event
def register_user(sid, data):
    """Регистрация пользователя"""
    try:
        username = data.get("username", f"user_{sid[:8]}")
        avatar = data.get("avatar", username[0].upper())

        connected_users[sid]["username"] = username
        connected_users[sid]["avatar"] = avatar
        connected_users[sid]["ready"] = False

        sio.emit(
            "user_registered",
            {
                "userId": sid,
                "username": username,
                "avatar": avatar,
                "status": "success",
            },
            room=sid,
        )

        print(f"[Socket.IO] Пользователь зарегистрирован: {username} ({sid})")

    except Exception as e:
        print(f"[Socket.IO] Ошибка регистрации: {e}")
        sio.emit("error", {"message": "Ошибка регистрации", "error": str(e)}, room=sid)


@sio.event
def create_session(sid, data):
    """Создание новой сессии программирования"""
    try:
        session_id = data.get("sessionId")
        session_type = data.get("type", "collaborative")
        session_name = data.get("name", "Новая сессия")
        task = data.get("task", {})
        creator = data.get("creator", {})

        if not session_id:
            session_id = f"session_{int(eventlet.time.time())}_{sid[:8]}"

        # Создаем сессию если ее еще нет
        if session_id not in active_sessions:
            active_sessions[session_id] = {
                "id": session_id,
                "type": session_type,
                "name": session_name,
                "task": task,
                "creator_sid": sid,
                "participants": [],
                "created_at": eventlet.format_isotime(eventlet.time.time()),
                "started": False,
                "code": task.get("template", ""),
            }

        # Получаем данные пользователя
        user_data = connected_users.get(sid, {})
        participant = {
            "sid": sid,
            "username": creator.get("username", user_data.get("username", "Unknown")),
            "avatar": creator.get("avatar", user_data.get("avatar", "U")),
            "ready": creator.get("ready", False),
            "is_creator": True,
        }

        # Добавляем создателя в сессию
        active_sessions[session_id]["participants"].append(participant)

        # Присоединяем пользователя к комнате сессии
        sio.enter_room(sid, session_id)

        # Отправляем подтверждение
        sio.emit(
            "session_created",
            {
                "sessionId": session_id,
                "name": session_name,
                "type": session_type,
                "task": task,
                "creator": participant,
            },
            room=sid,
        )

        print(f"[Socket.IO] Сессия создана: {session_id} ({session_name})")

    except Exception as e:
        print(f"[Socket.IO] Ошибка создания сессии: {e}")
        sio.emit(
            "error", {"message": "Ошибка создания сессии", "error": str(e)}, room=sid
        )


@sio.event
def invite_user(sid, data):
    """Приглашение пользователя в сессию"""
    try:
        session_id = data.get("sessionId")
        target_username = data.get("username")
        from_username = data.get("from")

        session = active_sessions.get(session_id)
        if not session:
            sio.emit("error", {"message": "Сессия не найдена"}, room=sid)
            return

        # Ищем пользователя среди подключенных
        target_sid = None
        for user_sid, user_data in connected_users.items():
            if user_data.get("username") == target_username:
                target_sid = user_sid
                break

        if not target_sid:
            sio.emit(
                "error",
                {"message": f"Пользователь {target_username} не найден или не в сети"},
                room=sid,
            )
            return

        # Отправляем приглашение
        sio.emit(
            "invitation_received",
            {
                "sessionId": session_id,
                "from": from_username,
                "fromUsername": from_username,
                "task": session["task"],
                "type": session["type"],
                "sessionName": session["name"],
            },
            room=target_sid,
        )

        # Уведомляем отправителя
        sio.emit(
            "invitation_sent",
            {"sessionId": session_id, "to": target_username, "status": "sent"},
            room=sid,
        )

        print(f"[Socket.IO] Приглашение отправлено: {target_username} -> {session_id}")

    except Exception as e:
        print(f"[Socket.IO] Ошибка отправки приглашения: {e}")
        sio.emit(
            "error",
            {"message": "Ошибка отправки приглашения", "error": str(e)},
            room=sid,
        )


@sio.event
def accept_invitation(sid, data):
    """Принятие приглашения"""
    try:
        session_id = data.get("sessionId")
        user = data.get("user", {})

        session = active_sessions.get(session_id)
        if not session:
            sio.emit("error", {"message": "Сессия не найдена"}, room=sid)
            return

        # Проверяем, не является ли пользователь уже участником
        existing_participant = any(p["sid"] == sid for p in session["participants"])
        if existing_participant:
            sio.emit("error", {"message": "Вы уже участник этой сессии"}, room=sid)
            return

        # Получаем данные пользователя
        user_data = connected_users.get(sid, {})
        participant = {
            "sid": sid,
            "username": user.get("username", user_data.get("username", "Unknown")),
            "avatar": user.get("avatar", user_data.get("avatar", "U")),
            "ready": user.get("ready", False),
            "is_creator": False,
        }

        # Добавляем пользователя в сессию
        session["participants"].append(participant)
        sio.enter_room(sid, session_id)

        # Уведомляем создателя сессии
        creator_sid = session["creator_sid"]
        sio.emit(
            "invitation_accepted",
            {
                "sessionId": session_id,
                "user": {
                    "username": participant["username"],
                    "avatar": participant["avatar"],
                    "socketId": sid,
                    "ready": participant["ready"],
                },
            },
            room=creator_sid,
        )

        # Отправляем текущий код новому участнику
        if "code" in session:
            sio.emit(
                "code_update",
                {
                    "sessionId": session_id,
                    "code": session["code"],
                    "from": creator_sid,
                    "timestamp": eventlet.format_isotime(eventlet.time.time()),
                },
                room=sid,
            )

        # Уведомляем всех участников о новом пользователе
        sio.emit(
            "user_joined",
            {
                "sessionId": session_id,
                "user": participant,
                "participants": session["participants"],
            },
            room=session_id,
        )

        print(
            f'[Socket.IO] Приглашение принято: {participant["username"]} -> {session_id}'
        )

    except Exception as e:
        print(f"[Socket.IO] Ошибка принятия приглашения: {e}")
        sio.emit(
            "error",
            {"message": "Ошибка принятия приглашения", "error": str(e)},
            room=sid,
        )


@sio.event
def user_ready(sid, data):
    """Обновление статуса готовности пользователя"""
    try:
        session_id = data.get("sessionId")
        is_ready = data.get("ready", False)

        session = active_sessions.get(session_id)
        if not session:
            return

        # Обновляем статус пользователя
        for participant in session["participants"]:
            if participant["sid"] == sid:
                participant["ready"] = is_ready
                break

        # Отправляем обновление всем участникам
        user_data = connected_users.get(sid, {})
        sio.emit(
            "user_ready_status",
            {
                "socketId": sid,
                "username": user_data.get("username", "Unknown"),
                "ready": is_ready,
                "sessionId": session_id,
            },
            room=session_id,
            skip_sid=sid,
        )

        # Проверяем, все ли готовы (только для дуэлей и совместных сессий)
        if len(session["participants"]) >= 2:
            all_ready = all(p.get("ready", False) for p in session["participants"])
            if all_ready and not session["started"]:
                session["started"] = True
                sio.emit(
                    "session_started",
                    {
                        "sessionId": session_id,
                        "participants": session["participants"],
                        "task": session["task"],
                    },
                    room=session_id,
                )
                print(f"[Socket.IO] Сессия начата: {session_id}")

    except Exception as e:
        print(f"[Socket.IO] Ошибка обновления статуса готовности: {e}")


@sio.event
def code_update(sid, data):
    """Обновление кода в сессии"""
    try:
        session_id = data.get("sessionId")
        code = data.get("code", "")
        user_id = data.get("userId")

        session = active_sessions.get(session_id)
        if not session:
            return

        # Сохраняем код в сессии
        session["code"] = code

        # Отправляем обновление всем участникам кроме отправителя
        sio.emit(
            "code_update",
            {
                "sessionId": session_id,
                "code": code,
                "from": user_id,
                "timestamp": eventlet.format_isotime(eventlet.time.time()),
            },
            room=session_id,
            skip_sid=sid,
        )

    except Exception as e:
        print(f"[Socket.IO] Ошибка обновления кода: {e}")


@sio.event
def chat_message(sid, data):
    """Отправка сообщения в чат"""
    try:
        session_id = data.get("sessionId")
        message = data.get("message", "")
        user = data.get("user", {})

        session = active_sessions.get(session_id)
        if not session:
            return

        # Отправляем сообщение всем участникам
        sio.emit(
            "chat_message",
            {
                "sessionId": session_id,
                "user": user,
                "message": message,
                "timestamp": eventlet.format_isotime(eventlet.time.time()),
            },
            room=session_id,
        )

    except Exception as e:
        print(f"[Socket.IO] Ошибка отправки сообщения: {e}")


@sio.event
def join_session(sid, data):
    """Присоединение к существующей сессии"""
    try:
        session_id = data.get("sessionId")

        session = active_sessions.get(session_id)
        if not session:
            sio.emit("error", {"message": "Сессия не найдена"}, room=sid)
            return

        # Проверяем, является ли пользователь участником
        participant = None
        for p in session["participants"]:
            if p["sid"] == sid:
                participant = p
                break

        if not participant:
            sio.emit("error", {"message": "Вы не участник этой сессии"}, room=sid)
            return

        # Присоединяем к комнате
        sio.enter_room(sid, session_id)

        # Отправляем текущее состояние сессии
        sio.emit(
            "session_state",
            {
                "sessionId": session_id,
                "participants": session["participants"],
                "code": session.get("code", ""),
                "task": session["task"],
                "started": session["started"],
            },
            room=sid,
        )

        print(
            f'[Socket.IO] Пользователь присоединился к сессии: {participant["username"]} -> {session_id}'
        )

    except Exception as e:
        print(f"[Socket.IO] Ошибка присоединения к сессии: {e}")
        sio.emit(
            "error",
            {"message": "Ошибка присоединения к сессии", "error": str(e)},
            room=sid,
        )


@sio.event
def leave_session(sid, data):
    """Выход из сессии"""
    try:
        session_id = data.get("sessionId")

        session = active_sessions.get(session_id)
        if not session:
            return

        # Удаляем пользователя из сессии
        removed_user = None
        session["participants"] = [
            p for p in session["participants"] if p["sid"] != sid or (removed_user := p)
        ]

        if removed_user:
            # Выходим из комнаты
            sio.leave_room(sid, session_id)

            # Уведомляем других участников
            sio.emit(
                "user_left",
                {
                    "sessionId": session_id,
                    "user": removed_user,
                    "participants": session["participants"],
                },
                room=session_id,
            )

            print(
                f'[Socket.IO] Пользователь вышел из сессии: {removed_user["username"]} -> {session_id}'
            )

    except Exception as e:
        print(f"[Socket.IO] Ошибка выхода из сессии: {e}")


@sio.event
def get_session_info(sid, data):
    """Получение информации о сессии"""
    try:
        session_id = data.get("sessionId")

        session = active_sessions.get(session_id)
        if not session:
            sio.emit("error", {"message": "Сессия не найдена"}, room=sid)
            return

        sio.emit(
            "session_info",
            {
                "sessionId": session_id,
                "name": session["name"],
                "type": session["type"],
                "task": session["task"],
                "participants": session["participants"],
                "started": session["started"],
                "createdAt": session["created_at"],
            },
            room=sid,
        )

    except Exception as e:
        print(f"[Socket.IO] Ошибка получения информации о сессии: {e}")
        sio.emit(
            "error",
            {"message": "Ошибка получения информации о сессии", "error": str(e)},
            room=sid,
        )


# Простое эхо для тестирования
@sio.event
def ping(sid, data):
    """Тестовое сообщение"""
    sio.emit(
        "pong",
        {"message": "pong", "timestamp": eventlet.format_isotime(eventlet.time.time())},
        room=sid,
    )


if __name__ == "__main__":
    print("=" * 50)
    print("Запуск Socket.IO сервера")
    print("=" * 50)

    # Запускаем сервер
    eventlet.wsgi.server(
        eventlet.listen(("0.0.0.0", 8001)),  # Порт 8001 для Socket.IO
        app,
        log=open("socketio.log", "w") if DEBUG else None,
    )
