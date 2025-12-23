from django.urls import path

from code_cup.apps import CodeCupConfig
from code_cup.views import main_page

app_name = CodeCupConfig.name

urlpatterns = [
    path("main/", main_page, name="main"),
]
