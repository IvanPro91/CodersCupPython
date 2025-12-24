from code_cup.models import UserTabs
from user.models import User


def register_handlers(sio_instance):
    """Регистрация обработчиков с передачей sio как параметра"""

    @sio_instance.event
    async def get_user_tabs(sid, data):
        session = await sio_instance.get_session(sid)
        user_id = session.get('user_id')
        username = session.get('username')
        user: User = await User.get_user(user_id)
        print(f"Пользователь: {username} (ID: {user_id})")
        user_tabs = await UserTabs.get_tabs(user)
        return {"status": "success", "user_tabs": user_tabs}

    @sio_instance.event
    async def close_user_tab(sid, data):
        tab_id = data.get("close_tab")
        session = await sio_instance.get_session(sid)
        user_id = session.get('user_id')
        username = session.get('username')
        user: User = await User.get_user(user_id)
        print(f"Пользователь: {username} (ID: {user_id})")
        user_tabs = await UserTabs.set_not_view(user, tab_id)
        return {"status": "success"}

    @sio_instance.event
    async def create_new_code_tab(sid, data):
        """Socket.IO запрос-ответ"""
        session = await sio_instance.get_session(sid)
        user_id = session.get('user_id')

        user: User = await User.get_user(user_id)
        type_tab: str = data.get("type")
        data_: dict = data.get("data_action")
        name: str = data_.get("name")

        find_user_code: UserTabs = await UserTabs.filter(type_tab, user, name)

        if not find_user_code:
            if type_tab == "single":
                template = data_.get("template")
                create_data = await UserTabs.add(user=user, type_tab=type_tab, name=name,
                                                  code=template, invited_username=None, task_type=None)
            elif type_tab == "duel":
                create_data = await UserTabs.add(user=user, type_tab=type_tab, name=name,
                                                  code="", invited_username=None, task_type=None)
            elif type_tab == "collaborative":
                invited_username = data_.get("invitedUsername")
                task_type = data_.get("taskType")
                create_data = await UserTabs.add(user=user, type_tab=type_tab, name=name,
                                                  code="", invited_username=invited_username, task_type=task_type)
            else:
                return {"status": "error", "message": "Неверный тип кода"}
        else:
            create_data = {}

        create_data["status"] = "success" if "status" not in create_data else "error"
        return create_data
