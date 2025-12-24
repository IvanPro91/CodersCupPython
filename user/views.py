import re
import uuid
from dataclasses import dataclass

from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.handlers.wsgi import WSGIRequest
from django.core.validators import ValidationError, validate_email
from django.http import JsonResponse, QueryDict
from django.shortcuts import redirect, render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from rest_framework_simplejwt.tokens import RefreshToken

from user.models import User

# Хранилище для временных данных пользователя
user_temp_data = {}


@dataclass
class CmdUser:
    status: bool
    msg: str
    access_token: str
    type_msg: str
    save: bool
    save_data: dict | None
    ask_next: bool
    next_question: str
    command_type: str
    is_password: bool = False  # Флаг, что следующий ввод - пароль
    is_sensitive: bool = False  # Флаг для чувствительных данных (пароли)
    redirect: bool = False  # Новое поле: нужно ли делать редирект
    redirect_url: str = ""  # Новое поле: URL для редиректа


def auth_page(request: WSGIRequest):
    # Очищаем временные данные при загрузке страницы
    # global user_temp_data
    if request.session.session_key in user_temp_data:
        del user_temp_data[request.session.session_key]

    # Проверяем, авторизован ли пользователь
    if request.user.is_authenticated:
        return redirect("code_cup:main")

    return render(request, "auth.html")


@login_required
def admin_console(request: WSGIRequest):
    """Страница админской консоли (только для авторизованных)"""
    return render(request, "admin_console.html")


def validate_username(username: str) -> tuple[bool, str]:
    """Проверка имени пользователя"""
    if not username:
        return False, "Username cannot be empty"

    if len(username) < 3:
        return False, "Username must be at least 3 characters long"

    if len(username) > 30:
        return False, "Username cannot exceed 30 characters"

    # Разрешаем только буквы, цифры, подчеркивания и точки
    if not re.match(r"^[a-zA-Z0-9_.]+$", username):
        return False, "Username can only contain letters, numbers, underscores and dots"

    # Нельзя начинать или заканчивать точкой
    if username.startswith(".") or username.endswith("."):
        return False, "Username cannot start or end with a dot"

    if ".." in username:
        return False, "Username cannot contain two consecutive dots"

    if User.objects.filter(username__iexact=username).exists():
        return False, f"Username '{username}' is already taken"

    return True, "Username is valid"


def validate_email_address(email: str) -> tuple[bool, str]:
    """Проверка email адреса"""
    if not email:
        return False, "Email cannot be empty"

    try:
        validate_email(email)
    except (ValidationError, DjangoValidationError):
        return False, "Invalid email format"

    if len(email) > 254:
        return False, "Email address is too long"

    domain = email.split("@")[1] if "@" in email else ""
    if not domain:
        return False, "Invalid email domain"

    if User.objects.filter(email__iexact=email).exists():
        return False, f"Email '{email}' is already registered"

    return True, "Email is valid"


def validate_password(password: str) -> tuple[bool, str]:
    """Проверка пароля"""
    if not password:
        return False, "Password cannot be empty"

    if len(password) < 8:
        return False, "Password must be at least 8 characters long"

    if len(password) > 128:
        return False, "Password is too long (max 128 characters)"

    if not re.search(r"\d", password):
        return False, "Password must contain at least one digit"

    if not re.search(r"[a-zA-Z]", password):
        return False, "Password must contain at least one letter"

    return True, "Password is valid"


@csrf_exempt
@require_POST
def commands(request: WSGIRequest):
    query_dict: QueryDict = request.POST
    cmd = query_dict.get("cmd", "")

    # Получаем или создаем сессию
    if not request.session.session_key:
        request.session.create()
    session_id = request.session.session_key

    data = CmdUser(
        status=False,
        msg=f"Command not found: {cmd}",
        type_msg="error",
        access_token="",
        save=False,
        save_data=None,
        ask_next=False,
        next_question="",
        command_type="",
        is_password=False,
        is_sensitive=False,
    )

    if session_id in user_temp_data and user_temp_data[session_id].get(
        "expecting_input"
    ):
        return process_multi_step_command(cmd, session_id, request)

    if cmd == "":
        data.status = False
        data.msg = "Please enter a command. Type 'help' for available commands."
        data.type_msg = "error"

    elif cmd == "status":
        if request.user.is_authenticated:
            data.status = True
            data.msg = (f"✅ System status: online\n📊 Active users: {User.objects.filter(is_active=True).count()}\n👤"
                        f" Logged in as: {request.user.username}\n⚡ Uptime: 24h")
            data.type_msg = "success"
        else:
            data.status = True
            data.msg = ("✅ System status: online\n🔒 Authentication required for full access\nType "
                        "'auth' to login or 'register' to create account")
            data.type_msg = "warning"

    elif cmd == "auth" or cmd == "login":
        if request.user.is_authenticated:
            data.status = True
            data.msg = f"You are already logged in as: {request.user.username}\nType 'logout' to exit"
            data.type_msg = "info"
            data.redirect = True
            data.redirect_url = "/code_cup/main/"
        else:
            user_temp_data[session_id] = {
                "expecting_input": True,
                "current_step": 1,
                "command": "auth",
                "collected_data": {},
                "current_field": "credentials",
            }

            data.status = True
            data.msg = "Starting authentication process..."
            data.type_msg = "info"
            data.ask_next = True
            data.next_question = (
                "Enter username and password (format: username password):"
            )
            data.command_type = "auth"
            data.is_sensitive = True

    elif cmd == "register" or cmd == "signup":
        if request.user.is_authenticated:
            data.status = True
            data.msg = (f"You are already logged in as: {request.user.username}\nType 'logout' "
                        f"to exit before registering new account")
            data.type_msg = "info"
        else:
            user_temp_data[session_id] = {
                "expecting_input": True,
                "current_step": 1,
                "total_steps": 5,
                "command": "register",
                "collected_data": {},
                "current_field": "username",
            }

            data.status = True
            data.msg = "Starting registration process..."
            data.type_msg = "info"
            data.ask_next = True
            data.next_question = "Enter username (3-30 chars, letters/numbers/_/.) or type 'cancel' to abort:"
            data.command_type = "register"

    elif cmd == "logout":
        if request.user.is_authenticated:
            logout(request)
            data.status = True
            data.msg = "✅ Successfully logged out. Goodbye!"
            data.type_msg = "success"
        else:
            data.status = False
            data.msg = "You are not logged in."
            data.type_msg = "error"

    elif cmd == "create user" or cmd == "add user":
        if not request.user.is_authenticated:
            data.status = False
            data.msg = "Authentication required. Type 'auth' to login first."
            data.type_msg = "error"
        elif not request.user.is_staff:
            data.status = False
            data.msg = "Permission denied. Admin privileges required."
            data.type_msg = "error"
        else:
            user_temp_data[session_id] = {
                "expecting_input": True,
                "current_step": 1,
                "total_steps": 5,
                "command": "create_user",
                "collected_data": {},
                "current_field": "username",
            }

            data.status = True
            data.msg = "Starting user creation process...\nFollow the prompts to create a new user."
            data.type_msg = "info"
            data.ask_next = True
            data.next_question = "Enter username (3-30 chars, letters/numbers/_/.) or type 'cancel' to abort:"
            data.command_type = "create_user"

    elif cmd == "help":
        if request.user.is_authenticated:
            if request.user.is_staff:
                data.status = True
                data.msg = (
                    "📋 Available commands:\n"
                    "• status - Check system status\n"
                    "• create user - Add new user (multi-step, admin only)\n"
                    "• logout - Logout from system\n"
                    "• clear - Clear terminal screen\n"
                    "• cancel - Cancel current operation\n"
                    "• help - Show this help"
                )
            else:
                data.status = True
                data.msg = (
                    "📋 Available commands:\n"
                    "• status - Check system status\n"
                    "• logout - Logout from system\n"
                    "• clear - Clear terminal screen\n"
                    "• cancel - Cancel current operation\n"
                    "• help - Show this help"
                )
            data.type_msg = "info"
        else:
            data.status = True
            data.msg = (
                "📋 Available commands:\n"
                "• status - Check system status\n"
                "• auth / login - Login to system\n"
                "• register / signup - Create new account\n"
                "• clear - Clear terminal screen\n"
                "• cancel - Cancel current operation\n"
                "• help - Show this help"
            )
            data.type_msg = "info"

    elif cmd == "clear":
        data.status = True
        data.msg = "clear"
        data.type_msg = "system"

    elif cmd == "cancel":
        if session_id in user_temp_data:
            del user_temp_data[session_id]
        data.status = True
        data.msg = "Operation cancelled."
        data.type_msg = "info"

    else:
        data.status = False
        data.msg = f"Unknown command: '{cmd}'\nType 'help' for available commands"
        data.type_msg = "error"

    return JsonResponse(data.__dict__)


def process_multi_step_command(
    cmd: str, session_id: str, request: WSGIRequest
) -> JsonResponse:
    if session_id not in user_temp_data:
        data = CmdUser(
            status=False,
            msg="Session expired. Please start over.",
            type_msg="error",
            access_token="",
            save=False,
            save_data=None,
            ask_next=False,
            next_question="",
            command_type="",
            is_password=False,
            is_sensitive=False,
        )
        return JsonResponse(data.__dict__)

    user_data = user_temp_data[session_id]
    current_step = user_data["current_step"]
    command_type = user_data["command"]

    data = CmdUser(
        status=False,
        msg="",
        type_msg="info",
        save=False,
        save_data=None,
        ask_next=False,
        next_question="",
        access_token="",
        command_type=command_type,
        is_password=False,
        is_sensitive=False,
    )

    if cmd.lower() == "cancel":
        del user_temp_data[session_id]
        data.status = True
        data.msg = "Operation cancelled."
        data.type_msg = "error"
        return JsonResponse(data.__dict__)

    if command_type == "auth":
        if current_step == 1:
            if not cmd:
                data.status = False
                data.msg = "Please enter username and password."
                data.type_msg = "error"
                data.ask_next = True
                data.next_question = (
                    "Enter username and password (format: username password):"
                )
                data.is_sensitive = True
                return JsonResponse(data.__dict__)

            parts = cmd.strip().split()
            if len(parts) < 2:
                data.status = False
                data.msg = "Invalid format. Please enter: username password"
                data.type_msg = "error"
                data.ask_next = True
                data.next_question = (
                    "Enter username and password (format: username password):"
                )
                data.is_sensitive = True
                return JsonResponse(data.__dict__)

            username = parts[0]
            password = " ".join(parts[1:])

            user = authenticate(request, username=username, password=password)

            if user is not None:
                login(request, user)

                data.status = True
                data.msg = f"Authentication successful!\n👤 Welcome, {user.username}!"
                refresh = RefreshToken.for_user(user)
                access_token = str(refresh.access_token)
                if user.is_staff:
                    data.msg += "\n⚡ Admin privileges granted."
                data.type_msg = "success"
                data.redirect = True
                data.access_token = access_token
                data.redirect_url = "/code_cup/main/"

                del user_temp_data[session_id]
            else:
                data.status = False
                data.msg = "Invalid username or password."
                data.type_msg = "error"
                data.ask_next = True
                data.next_question = (
                    "Enter username and password (format: username password):"
                )
                data.is_sensitive = True

    elif command_type == "register":
        if current_step == 1:
            if not cmd:
                data.status = False
                data.msg = "Username is required. Please enter a username."
                data.type_msg = "error"
                data.ask_next = True
                data.next_question = "Enter username (3-30 chars, letters/numbers/_/.) or type 'cancel' to abort:"
                return JsonResponse(data.__dict__)

            is_valid, validation_msg = validate_username(cmd)

            if not is_valid:
                data.status = False
                data.msg = f"{validation_msg}"
                data.type_msg = "error"
                data.ask_next = True
                data.next_question = "Enter username (3-30 chars, letters/numbers/_/.) or type 'cancel' to abort:"
                return JsonResponse(data.__dict__)

            user_data["collected_data"]["username"] = cmd
            user_data["current_step"] = 2
            user_data["current_field"] = "email"

            data.status = True
            data.msg = f"Username '{cmd}' is available and valid."
            data.type_msg = "success"
            data.ask_next = True
            data.next_question = "Enter email address or type 'cancel' to abort:"

        elif current_step == 2:  # Email
            if not cmd:
                data.status = False
                data.msg = "Email is required. Please enter an email address."
                data.type_msg = "error"
                data.ask_next = True
                data.next_question = "Enter email address or type 'cancel' to abort:"
                return JsonResponse(data.__dict__)

            is_valid, validation_msg = validate_email_address(cmd)

            if not is_valid:
                data.status = False
                data.msg = f"{validation_msg}"
                data.type_msg = "error"
                data.ask_next = True
                data.next_question = "Enter email address or type 'cancel' to abort:"
                return JsonResponse(data.__dict__)

            user_data["collected_data"]["email"] = cmd
            user_data["current_step"] = 3
            user_data["current_field"] = "first_name"

            data.status = True
            data.msg = f"Email '{cmd}' is valid and available."
            data.type_msg = "success"
            data.ask_next = True
            data.next_question = "Enter first name (optional, press Enter to skip) or type 'cancel' to abort:"

        elif current_step == 3:
            user_data["collected_data"]["first_name"] = cmd if cmd else ""
            user_data["current_step"] = 4
            user_data["current_field"] = "last_name"

            data.status = True
            if cmd:
                data.msg = f"First name '{cmd}' saved."
            else:
                data.msg = "Skipped first name."
            data.type_msg = "success"
            data.ask_next = True
            data.next_question = "Enter last name (optional, press Enter to skip) or type 'cancel' to abort:"

        elif current_step == 4:
            user_data["collected_data"]["last_name"] = cmd if cmd else ""
            user_data["current_step"] = 5
            user_data["current_field"] = "password"

            data.status = True
            if cmd:
                data.msg = f"Last name '{cmd}' saved."
            else:
                data.msg = "Skipped last name."
            data.type_msg = "success"
            data.ask_next = True
            data.next_question = ("Enter password (min 8 chars, at least 1 letter & 1 number) "
                                  "or type 'cancel' to abort:")
            data.is_password = True

        elif current_step == 5:
            if not cmd:
                data.status = False
                data.msg = "Password is required. Please enter a password."
                data.type_msg = "error"
                data.ask_next = True
                data.next_question = ("Enter password (min 8 chars, at least 1 letter & 1 number) "
                                      "or type 'cancel' to abort:")
                data.is_password = True
                return JsonResponse(data.__dict__)

            is_valid, validation_msg = validate_password(cmd)

            if not is_valid:
                data.status = False
                data.msg = f"{validation_msg}"
                data.type_msg = "error"
                data.ask_next = True
                data.next_question = ("Enter password (min 8 chars, at least 1 letter & 1 number) "
                                      "or type 'cancel' to abort:")
                data.is_password = True
                return JsonResponse(data.__dict__)

            user_data["collected_data"]["password"] = cmd
            user_data["current_step"] = 6
            user_data["current_field"] = "confirm_password"

            data.status = True
            data.msg = "Password meets requirements."
            data.type_msg = "success"
            data.ask_next = True
            data.next_question = "Confirm password or type 'cancel' to abort:"
            data.is_password = True

        elif current_step == 6:

            if not cmd:
                data.status = False
                data.msg = "Please confirm the password."
                data.type_msg = "error"
                data.ask_next = True
                data.next_question = "Confirm password or type 'cancel' to abort:"
                data.is_password = True
                return JsonResponse(data.__dict__)

            if cmd != user_data["collected_data"]["password"]:
                data.status = False
                data.msg = "Passwords don't match. Please try again."
                data.type_msg = "error"
                data.ask_next = True
                data.next_question = ("Enter password (min 8 chars, at least 1 letter & 1 number) "
                                      "or type 'cancel' to abort:")
                data.is_password = True
                user_data["current_step"] = 5
                user_data["current_field"] = "password"
                return JsonResponse(data.__dict__)

            collected_data = user_data["collected_data"]

            try:
                user = User.objects.create_user(
                    username=collected_data["username"],
                    email=collected_data["email"],
                    password=collected_data["password"],
                    first_name=collected_data.get("first_name", ""),
                    last_name=collected_data.get("last_name", ""),
                    is_active=True,
                    token=str(uuid.uuid4()),
                )
                login(request, user)
                refresh = RefreshToken.for_user(user)
                access_token = str(refresh.access_token)
                data.status = True
                data.msg = (
                    f"Registration successful!\n"
                    f"Account created for '{collected_data['username']}'\n"
                    f"Email: {collected_data['email']}\n"
                    f"Registered: {user.date_joined.strftime('%Y-%m-%d %H:%M')}\n"
                    f"Automatically logged in!\n"
                    f"Redirecting to main page..."
                )
                data.type_msg = "success"
                data.save = True
                data.access_token = access_token
                data.save_data = {
                    "id": user.id,
                    "username": user.username,
                    "email": user.email,
                    "first_name": user.first_name,
                    "last_name": user.last_name,
                    "date_joined": user.date_joined.strftime("%Y-%m-%d %H:%M:%S"),
                }
                data.redirect = True
                data.redirect_url = "/code_cup/main/"

            except Exception as e:
                data.status = False
                data.msg = f"Error creating account: {str(e)}"
                data.type_msg = "error"

            if session_id in user_temp_data:
                del user_temp_data[session_id]

    elif command_type == "create_user":
        if current_step == 1:
            if not cmd:
                data.status = False
                data.msg = "Username is required. Please enter a username."
                data.type_msg = "error"
                data.ask_next = True
                data.next_question = "Enter username (3-30 chars, letters/numbers/_/.) or type 'cancel' to abort:"
                return JsonResponse(data.__dict__)

            is_valid, validation_msg = validate_username(cmd)

            if not is_valid:
                data.status = False
                data.msg = f"{validation_msg}"
                data.type_msg = "error"
                data.ask_next = True
                data.next_question = "Enter username (3-30 chars, letters/numbers/_/.) or type 'cancel' to abort:"
                return JsonResponse(data.__dict__)

            user_data["collected_data"]["username"] = cmd
            user_data["current_step"] = 2
            user_data["current_field"] = "email"

            data.status = True
            data.msg = f"Username '{cmd}' is available and valid."
            data.type_msg = "success"
            data.ask_next = True
            data.next_question = "Enter email address or type 'cancel' to abort:"

        elif current_step == 2:
            if not cmd:
                data.status = False
                data.msg = "Email is required. Please enter an email address."
                data.type_msg = "error"
                data.ask_next = True
                data.next_question = "Enter email address or type 'cancel' to abort:"
                return JsonResponse(data.__dict__)

            is_valid, validation_msg = validate_email_address(cmd)

            if not is_valid:
                data.status = False
                data.msg = f"{validation_msg}"
                data.type_msg = "error"
                data.ask_next = True
                data.next_question = "Enter email address or type 'cancel' to abort:"
                return JsonResponse(data.__dict__)

            user_data["collected_data"]["email"] = cmd
            user_data["current_step"] = 3
            user_data["current_field"] = "first_name"

            data.status = True
            data.msg = f"✅ Email '{cmd}' is valid and available."
            data.type_msg = "success"
            data.ask_next = True
            data.next_question = "Enter first name (optional, press Enter to skip) or type 'cancel' to abort:"

        elif current_step == 3:
            user_data["collected_data"]["first_name"] = cmd if cmd else ""
            user_data["current_step"] = 4
            user_data["current_field"] = "last_name"

            data.status = True
            if cmd:
                data.msg = f"First name '{cmd}' saved."
            else:
                data.msg = "Skipped first name."
            data.type_msg = "success"
            data.ask_next = True
            data.next_question = "Enter last name (optional, press Enter to skip) or type 'cancel' to abort:"

        elif current_step == 4:  # Фамилия (опциональное поле)
            user_data["collected_data"]["last_name"] = cmd if cmd else ""
            user_data["current_step"] = 5
            user_data["current_field"] = "password"

            data.status = True
            if cmd:
                data.msg = f"Last name '{cmd}' saved."
            else:
                data.msg = "Skipped last name."
            data.type_msg = "success"
            data.ask_next = True
            data.next_question = ("Enter password (min 8 chars, at least 1 letter & 1 number) "
                                  "or type 'cancel' to abort:")
            data.is_password = True

        elif current_step == 5:  # Пароль
            if not cmd:
                data.status = False
                data.msg = "Password is required. Please enter a password."
                data.type_msg = "error"
                data.ask_next = True
                data.next_question = ("Enter password (min 8 chars, at least 1 letter & 1 number) "
                                      "or type 'cancel' to abort:")
                data.is_password = True
                return JsonResponse(data.__dict__)

            is_valid, validation_msg = validate_password(cmd)

            if not is_valid:
                data.status = False
                data.msg = f"{validation_msg}"
                data.type_msg = "error"
                data.ask_next = True
                data.next_question = ("Enter password (min 8 chars, at least 1 letter & 1 number) "
                                      "or type 'cancel' to abort:")
                data.is_password = True
                return JsonResponse(data.__dict__)

            user_data["collected_data"]["password"] = cmd
            user_data["current_step"] = 6
            user_data["current_field"] = "confirm_password"

            data.status = True
            data.msg = "Password meets requirements."
            data.type_msg = "success"
            data.ask_next = True
            data.next_question = "Confirm password or type 'cancel' to abort:"
            data.is_password = True

        elif current_step == 6:  # Подтверждение пароля
            if not cmd:
                data.status = False
                data.msg = "Please confirm the password."
                data.type_msg = "error"
                data.ask_next = True
                data.next_question = "Confirm password or type 'cancel' to abort:"
                data.is_password = True
                return JsonResponse(data.__dict__)

            if cmd != user_data["collected_data"]["password"]:
                data.status = False
                data.msg = "Passwords don't match. Please try again."
                data.type_msg = "error"
                data.ask_next = True
                data.next_question = ("Enter password (min 8 chars, at least 1 letter & 1 number) "
                                      "or type 'cancel' to abort:")
                data.is_password = True
                user_data["current_step"] = 5
                user_data["current_field"] = "password"
                return JsonResponse(data.__dict__)

            collected_data = user_data["collected_data"]

            try:
                user = User.objects.create_user(
                    username=collected_data["username"],
                    email=collected_data["email"],
                    password=collected_data["password"],
                    first_name=collected_data.get("first_name", ""),
                    last_name=collected_data.get("last_name", ""),
                    is_active=True,
                    token=str(uuid.uuid4()),
                )

                data.status = True
                data.msg = (
                    f"User '{collected_data['username']}' created successfully!\n"
                    f"Email: {collected_data['email']}\n"
                    f"ID: {user.id}\n"
                    f"Created: {user.date_joined.strftime('%Y-%m-%d %H:%M')}"
                )
                data.type_msg = "success"
                data.save = True
                data.save_data = {
                    "username": user.username,
                    "email": user.email,
                    "first_name": user.first_name,
                    "last_name": user.last_name,
                    "date_joined": user.date_joined.strftime("%Y-%m-%d %H:%M:%S"),
                }

            except Exception as e:
                data.status = False
                data.msg = f"Error creating user: {str(e)}"
                data.type_msg = "error"

            if session_id in user_temp_data:
                del user_temp_data[session_id]

        else:
            data.status = False
            data.msg = "Invalid step in user creation"
            data.type_msg = "error"
            if session_id in user_temp_data:
                del user_temp_data[session_id]

    return JsonResponse(data.__dict__)
