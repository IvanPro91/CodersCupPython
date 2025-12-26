import json

from django.contrib.auth.decorators import login_required
from django.core.handlers.wsgi import WSGIRequest
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import JsonResponse, Http404, QueryDict
from django.shortcuts import render
from django.views.decorators.http import require_POST, require_GET
from django.views.decorators.csrf import csrf_exempt

from code_cup.models import UserTabs, Task
from code_cup.tasks import execute_user_code
from code_cup.views_utils import CodeSecurityChecker
from celery.result import AsyncResult

@login_required(login_url="/")
def main_page(request):
    return render(request, "main_page.html")

@login_required(login_url="/")
@csrf_exempt
@require_POST
def get_page_editor(request: WSGIRequest):
    data: QueryDict = request.POST
    print(data)
    return JsonResponse({"stata": True})

@login_required(login_url="/")
@csrf_exempt
@require_GET
def tab_content_view(request: WSGIRequest, id_tab_view: int):
    get_tab: UserTabs = UserTabs.objects.filter(pk = id_tab_view, is_view = True).first()
    if get_tab.user == request.user:
        if get_tab.type_tab == "single":
            return render(request, "content/single_editor.html",
                          context={
                               "tab_id": get_tab.pk,
                               "name": get_tab.name,
                               "code": get_tab.code
                          })
    raise Http404("Page not found.")

@csrf_exempt
@require_GET
def get_status(request, task_id):
    result = AsyncResult(task_id)
    response = {
        'status': result.status, # PENDING, STARTED, SUCCESS, FAILURE
        'result': result.result if result.ready() else None
    }
    return JsonResponse(response)

@csrf_exempt
def run_code(request):
    code = request.POST.get('code', '').strip()
    id_task = request.POST.get('task')

    is_safe, msg = CodeSecurityChecker.check_code_security(code)
    if not is_safe:
        return JsonResponse({'success': False, 'error': msg})

    # Запускаем задачу асинхронно
    task = execute_user_code.delay(id_task, code)

    return JsonResponse({
        'success': True,
        'task_id': task.id
    })


# code_cup/views.py
@csrf_exempt
def get_task_details(request, task_id):
    """Получение детальной информации о задаче"""
    if request.method != 'GET':
        return JsonResponse({'error': 'Method not allowed'}, status=405)

    try:
        task = Task.objects.get(id=task_id, is_active=True)

        # Получаем количество тестов и подсказок
        test_cases_count = task.test_cases.count()
        hints_count = task.task_hints.count()

        # Парсим JSON поля
        try:
            tags = json.loads(task.tags_json) if task.tags_json else []
        except:
            tags = []

        task_data = {
            'id': task.id,
            'num': task.num,
            'name': task.name,
            'description': task.task_text,
            'formatted_description': task.get_formatted_task_text(),
            'level': task.level,
            'level_display': task.get_level_display(),
            'category': task.category,
            'category_display': task.get_category_display(),
            'time_limit': task.time_limit,
            'memory_limit': task.memory_limit,
            'code_template': task.code,
            'tags': tags,
            'test_cases_count': test_cases_count,
            'hints_count': hints_count,
            'created_at': task.created_at.strftime('%d.%m.%Y'),
        }

        return JsonResponse(task_data)

    except Task.DoesNotExist:
        return JsonResponse({'error': 'Task not found'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)




@csrf_exempt
def search_tasks(request):
    """Поиск задач по названию и описанию"""
    if request.method != 'GET':
        return JsonResponse({'error': 'Method not allowed'}, status=405)

    query = request.GET.get('q', '').strip()
    level = request.GET.get('level', '').strip()
    category = request.GET.get('category', '').strip()
    page = int(request.GET.get('page', 1))
    per_page = int(request.GET.get('per_page', 10))

    try:
        # Базовый запрос только активных задач
        tasks = Task.objects.filter(is_active=True)

        # Фильтрация по поисковому запросу
        if query:
            tasks = tasks.filter(
                Q(name__icontains=query) |
                Q(num__icontains=query) |
                Q(task_text__icontains=query)
            )

        # Фильтрация по уровню сложности
        if level:
            tasks = tasks.filter(level=level)

        # Фильтрация по категории
        if category:
            tasks = tasks.filter(category=category)

        # Пагинация
        paginator = Paginator(tasks, per_page)
        page_obj = paginator.get_page(page)

        # Формирование ответа
        tasks_data = []
        for task in page_obj:
            # Парсим JSON поля
            try:
                tags = json.loads(task.tags_json) if task.tags_json else []
            except:
                tags = []

            task_data = {
                'id': task.id,
                'num': task.num,
                'name': task.name,
                'description': task.task_text[:150] + '...' if len(task.task_text) > 150 else task.task_text,
                'level': task.level,
                'level_display': task.get_level_display(),
                'category': task.category,
                'category_display': task.get_category_display(),
                'time_limit': task.time_limit,
                'memory_limit': task.memory_limit,
                'tags': tags,
                'hints_count': task.task_hints.count(),
                'test_cases_count': task.test_cases.count(),
            }
            tasks_data.append(task_data)

        response = {
            'tasks': tasks_data,
            'total': paginator.count,
            'page': page,
            'per_page': per_page,
            'total_pages': paginator.num_pages,
            'has_next': page_obj.has_next(),
            'has_previous': page_obj.has_previous(),
        }

        return JsonResponse(response)

    except Exception as e:
        return JsonResponse({
            'error': str(e),
            'tasks': [],
            'total': 0,
            'page': 1,
            'per_page': per_page,
            'total_pages': 0
        }, status=500)