from django.urls import path

from user.apps import UserConfig
from user.views import auth_page, commands

app_name = UserConfig.name

urlpatterns = [
    path("", auth_page, name=""),
    path("commands/", commands, name="commands"),
]
