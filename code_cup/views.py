from django.contrib.auth.decorators import login_required
from django.core.handlers.wsgi import WSGIRequest
from django.http import JsonResponse, Http404, QueryDict
from django.shortcuts import render
from django.views.decorators.http import require_POST, require_GET
from django.views.decorators.csrf import csrf_exempt

from code_cup.models import UserTabs
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

    is_safe, msg = CodeSecurityChecker.check_code_security(code)
    if not is_safe:
        return JsonResponse({'success': False, 'error': msg})

    # Запускаем задачу асинхронно
    print(code)
    task = execute_user_code.delay(1, code)

    return JsonResponse({
        'success': True,
        'task_id': task.id  # Фронтенд запомнит этот ID
    })