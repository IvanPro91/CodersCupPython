import json
from typing import Any

from channels.generic.websocket import AsyncWebsocketConsumer
from django.contrib.auth.models import AnonymousUser

from code_cup.models import UserTabs


class CodeCupWebSocket(AsyncWebsocketConsumer):
    def __init__(self, *args, **kwargs):
        """Инициализация объекта"""
        super().__init__(args, kwargs)
        self.room_name = None
        self.room_group_name = None
        self.user = None

    async def connect(self):
        """Подключение к серверу"""
        try:
            # Получаем room_name из URL
            self.room_name = self.scope["url_route"]["kwargs"]["room_name"]
            self.room_group_name = f"chat_{self.room_name}"
            self.user = self.scope.get("user", AnonymousUser())

            if self.user.token == self.room_name:
                print(
                    f"🔗 Подключение: комната={self.room_name}, пользователь={self.user}"
                )

                # Присоединяемся к группе комнаты
                await self.channel_layer.group_add(
                    self.room_group_name, self.channel_name
                )

                # Принимаем соединение
                await self.accept()

                # Отправляем приветственное сообщение
                await self.send(
                    text_data=json.dumps(
                        {
                            "type": "system",
                            "message": f"Вы подключились к комнате {self.room_name}",
                            "sender": "Система",
                        }
                    )
                )

            # # Уведомляем других о подключении (опционально)
            # if not isinstance(self.user, AnonymousUser):
            #     await self.channel_layer.group_send(
            #         self.room_group_name,
            #         {
            #             'type': 'user_connected',
            #             'user_id': str(self.user.id),
            #             'username': user_info
            #         }
            #     )
        except Exception as e:
            print(f"Ошибка подключения: {e}")
            await self.close()

    async def disconnect(self, close_code):
        """Отключение от сервера"""
        print(f"Отключение от комнаты {self.room_name}, код: {close_code}")
        # Выходим из группы
        await self.channel_layer.group_discard(self.room_group_name, self.channel_name)

    async def receive(self, text_data: Any):
        """Получение сообщения от клиента"""
        try:
            data: dict = json.loads(text_data)
            action = data.get("action")
            if action == "create_new_code_tab":
                await self.create_new_code_tab(data)
        except Exception as err:
            await self.send(
                text_data=json.dumps(
                    {"status": "error", "message": f"Неверный формат данных -> {err}"}
                )
            )

    async def create_new_code_tab(self, data: dict):
        """Создание нового кода"""
        type_: str = data.get("type")
        data_: dict = data.get("data")
        name: str = data_.get("name")

        find_user_code: UserTabs = UserTabs.objects.filter(
            type_=type_, user=self.user, name=name
        ).first()
        if not find_user_code:
            if type_ == "single":
                template = data_.get("template")
                # Тут проверяем в БД данные и возвращаем результат
                pass
            elif type_ == "duel":
                # Тут проверяем в БД данные и возвращаем результат
                pass
            elif type_ == "collaborative":
                invited_username = data_.get("invitedUsername")
                task_type = data_.get("taskType")
                # Тут проверяем в БД данные и возвращаем результат
                pass
            else:
                await self.send(
                    text_data=json.dumps(
                        {"status": "error", "message": "Неверный тип кода"}
                    )
                )

        print(data)
        pass
