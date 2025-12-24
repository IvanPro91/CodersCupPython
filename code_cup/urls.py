from django.urls import path

from code_cup.apps import CodeCupConfig
from code_cup.views import main_page, get_page_editor, tab_content_view, run_code

app_name = CodeCupConfig.name

urlpatterns = [
    path("main/", main_page, name="main"),
    path("editor/", get_page_editor, name="page_editor"),
    path("editor/get_editor/<int:id_tab_view>/", tab_content_view, name="tab_content_view"),
    path('editor/run-code/', run_code, name='run_code'),
]
