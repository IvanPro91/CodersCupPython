from django.urls import path

from code_cup.apps import CodeCupConfig
from code_cup.views import main_page, get_page_editor, tab_content_view, run_code, get_status, search_tasks, get_task_details

app_name = CodeCupConfig.name

urlpatterns = [
    path("main/", main_page, name="main"),
    path("editor/", get_page_editor, name="page_editor"),
    path("editor/get_editor/<int:id_tab_view>/", tab_content_view, name="tab_content_view"),
    path('editor/run-code/', run_code, name='run_code'),
    path('editor/get-status/<str:task_id>/', get_status, name='get_status'),
    path('editor/tasks/search/', search_tasks, name='search_tasks'),
    path('editor/tasks/<int:task_id>/details/', get_task_details, name='get_task_details'),
    # path('editor/tasks/<int:task_id>/template/', get_task_template, name='get_task_template'),
]
