import ast
import json
import time

from django.contrib.auth.decorators import login_required
from django.core.handlers.wsgi import WSGIRequest
from django.http import QueryDict, JsonResponse, Http404
from django.shortcuts import render
from django.views.decorators.http import require_POST, require_GET
from code_cup.models import UserTabs
from django.views.decorators.csrf import csrf_exempt
from io import StringIO
import contextlib


# Запрещенные команды и модули
FORBIDDEN_COMMANDS = [
    'os.system', 'subprocess', 'eval', 'exec', '__import__', 'open',
    'compile', 'globals', 'locals', 'getattr', 'setattr', 'delattr'
]

FORBIDDEN_MODULES = [
    'os', 'sys', 'subprocess', 'shutil', 'socket', 'threading',
    'multiprocessing', 'ctypes', 'mmap', 'resource', 'pty', 'fcntl'
]


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




class CodeSecurityChecker:
    @staticmethod
    def check_code_security(code):
        """Проверка кода на наличие опасных конструкций"""
        try:
            tree = ast.parse(code)

            for node in ast.walk(tree):
                # Проверка импортов
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        if alias.name in FORBIDDEN_MODULES:
                            return False, f"Запрещенный импорт: {alias.name}"

                # Проверка импортов из модулей
                if isinstance(node, ast.ImportFrom):
                    if node.module in FORBIDDEN_MODULES:
                        return False, f"Запрещенный импорт из: {node.module}"

                # Проверка вызовов функций
                if isinstance(node, ast.Call):
                    if isinstance(node.func, ast.Name):
                        if node.func.id in FORBIDDEN_COMMANDS:
                            return False, f"Запрещенная функция: {node.func.id}"

                    # Проверка атрибутов
                    if isinstance(node.func, ast.Attribute):
                        attr_name = node.func.attr
                        if attr_name in FORBIDDEN_COMMANDS:
                            return False, f"Запрещенный метод: {attr_name}"

                        # Проверка os.system и подобных
                        if isinstance(node.func.value, ast.Name):
                            if node.func.value.id in FORBIDDEN_MODULES:
                                return False, f"Запрещенный вызов: {node.func.value.id}.{attr_name}"

            return True, "Код безопасен"

        except SyntaxError as e:
            return False, f"Синтаксическая ошибка: {str(e)}"


class SafeCodeRunner:
    @staticmethod
    def execute_line_by_line(code):
        """Выполнение кода построчно с захватом вывода"""
        lines = code.split('\n')
        results = []
        local_vars = {}
        global_vars = {'__builtins__': {}}

        # Создаем безопасное пространство имен
        safe_builtins = {
            'print': print,
            'len': len,
            'str': str,
            'int': int,
            'float': float,
            'list': list,
            'dict': dict,
            'tuple': tuple,
            'set': set,
            'range': range,
            'bool': bool,
            'type': type,
            'sum': sum,
            'max': max,
            'min': min,
            'abs': abs,
            'round': round,
            'sorted': sorted,
            'enumerate': enumerate,
            'zip': zip
        }

        global_vars['__builtins__'] = safe_builtins

        for i, line in enumerate(lines):
            line = line.strip()
            if not line or line.startswith('#'):
                results.append({
                    'line': i + 1,
                    'code': line,
                    'output': '',
                    'success': True,
                    'error': None
                })
                continue

            try:
                # Захватываем вывод print
                output_buffer = StringIO()
                with contextlib.redirect_stdout(output_buffer):
                    # Пытаемся выполнить как выражение
                    try:
                        compiled = compile(line, '<string>', 'eval')
                        result = eval(compiled, global_vars, local_vars)
                        output = str(result) if result is not None else ''

                        # Сохраняем результат в локальные переменные
                        if '=' in line and not line.strip().startswith('if') and not line.strip().startswith('for'):
                            var_name = line.split('=')[0].strip()
                            local_vars[var_name] = result

                    except SyntaxError:
                        # Если не выражение, выполняем как statement
                        compiled = compile(line, '<string>', 'exec')
                        exec(compiled, global_vars, local_vars)
                        output = output_buffer.getvalue().strip()

                results.append({
                    'line': i + 1,
                    'code': line,
                    'output': output,
                    'success': True,
                    'error': None
                })

            except Exception as e:
                results.append({
                    'line': i + 1,
                    'code': line,
                    'output': None,
                    'success': False,
                    'error': str(e)
                })

        return results

    @staticmethod
    def analyze_code(code):
        """Анализ кода: подсчет функций и классов"""
        functions_count = 0
        classes_count = 0

        try:
            tree = ast.parse(code)

            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    functions_count += 1
                elif isinstance(node, ast.ClassDef):
                    classes_count += 1

        except:
            pass

        return functions_count, classes_count


class CodeSecurityChecker:
    @staticmethod
    def check_code_security(code):
        """Проверка кода на наличие опасных конструкций"""
        try:
            tree = ast.parse(code)

            for node in ast.walk(tree):
                # Проверка импортов
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        if alias.name in FORBIDDEN_MODULES:
                            return False, f"Запрещенный импорт: {alias.name}"

                # Проверка импортов из модулей
                if isinstance(node, ast.ImportFrom):
                    if node.module in FORBIDDEN_MODULES:
                        return False, f"Запрещенный импорт из: {node.module}"

                # Проверка вызовов функций
                if isinstance(node, ast.Call):
                    if isinstance(node.func, ast.Name):
                        if node.func.id in FORBIDDEN_COMMANDS:
                            return False, f"Запрещенная функция: {node.func.id}"

                    # Проверка атрибутов
                    if isinstance(node.func, ast.Attribute):
                        attr_name = node.func.attr
                        if attr_name in FORBIDDEN_COMMANDS:
                            return False, f"Запрещенный метод: {attr_name}"

                        # Проверка os.system и подобных
                        if isinstance(node.func.value, ast.Name):
                            if node.func.value.id in FORBIDDEN_MODULES:
                                return False, f"Запрещенный вызов: {node.func.value.id}.{attr_name}"

            return True, "Код безопасен"

        except SyntaxError as e:
            return False, f"Синтаксическая ошибка: {str(e)}"


class CodeSecurityChecker:
    @staticmethod
    def check_code_security(code):
        """Проверка кода на наличие опасных конструкций"""
        try:
            tree = ast.parse(code)

            for node in ast.walk(tree):
                # Проверка импортов
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        if alias.name in FORBIDDEN_MODULES:
                            return False, f"Запрещенный импорт: {alias.name}"

                # Проверка импортов из модулей
                if isinstance(node, ast.ImportFrom):
                    if node.module in FORBIDDEN_MODULES:
                        return False, f"Запрещенный импорт из: {node.module}"

                # Проверка вызовов функций
                if isinstance(node, ast.Call):
                    if isinstance(node.func, ast.Name):
                        if node.func.id in FORBIDDEN_COMMANDS:
                            return False, f"Запрещенная функция: {node.func.id}"

                    # Проверка атрибутов
                    if isinstance(node.func, ast.Attribute):
                        attr_name = node.func.attr
                        if attr_name in FORBIDDEN_COMMANDS:
                            return False, f"Запрещенный метод: {attr_name}"

                        # Проверка os.system и подобных
                        if isinstance(node.func.value, ast.Name):
                            if node.func.value.id in FORBIDDEN_MODULES:
                                return False, f"Запрещенный вызов: {node.func.value.id}.{attr_name}"

            return True, "Код безопасен"

        except SyntaxError as e:
            return False, f"Синтаксическая ошибка: {str(e)}"


class SafeCodeRunner:
    @staticmethod
    def execute_code(code):
        """Выполнение кода с захватом вывода и детальным анализом"""
        # Создаем безопасное пространство имен
        safe_builtins = {
            'print': print,
            'len': len,
            'str': str,
            'int': int,
            'float': float,
            'list': list,
            'dict': dict,
            'tuple': tuple,
            'set': set,
            'range': range,
            'bool': bool,
            'type': type,
            'sum': sum,
            'max': max,
            'min': min,
            'abs': abs,
            'round': round,
            'sorted': sorted,
            'enumerate': enumerate,
            'zip': zip
        }

        global_vars = {'__builtins__': safe_builtins}
        output_buffer = StringIO()
        lines = code.split('\n')
        results = []

        try:
            # Сначала выполняем весь код для получения общего вывода
            with contextlib.redirect_stdout(output_buffer):
                exec(code, global_vars, {})

            full_output = output_buffer.getvalue().strip()
            output_lines = full_output.split('\n') if full_output else []

            # Создаем детализированные результаты для каждой строки
            output_index = 0

            for i, line in enumerate(lines):
                line_num = i + 1
                line_text = line.rstrip()

                if not line_text:
                    # Пустая строка
                    results.append({
                        'line': line_num,
                        'code': '',
                        'output': '',
                        'success': True,
                        'error': None
                    })
                    continue

                # Проверяем, является ли строка определением функции/класса
                is_definition = line_text.endswith(':') or line_text.startswith(
                    ('def ', 'class ', 'if ', 'for ', 'while '))

                # Определяем вывод для строки
                line_output = ''
                if output_index < len(output_lines) and not is_definition:
                    # Присваиваем вывод только исполняемым строкам
                    line_output = output_lines[output_index]
                    output_index += 1

                results.append({
                    'line': line_num,
                    'code': line_text,
                    'output': line_output,
                    'success': True,
                    'error': None
                })

            return results, full_output

        except Exception as e:
            # Если есть ошибка, возвращаем информацию о ней
            error_line = 1
            error_msg = str(e)

            # Пытаемся определить строку с ошибкой
            if 'line' in error_msg.lower():
                import re
                match = re.search(r'line (\d+)', error_msg)
                if match:
                    error_line = int(match.group(1))

            for i, line in enumerate(lines):
                line_num = i + 1
                line_text = line.rstrip()

                if line_num == error_line:
                    results.append({
                        'line': line_num,
                        'code': line_text,
                        'output': None,
                        'success': False,
                        'error': error_msg
                    })
                else:
                    results.append({
                        'line': line_num,
                        'code': line_text,
                        'output': '',
                        'success': True if line_num < error_line else False,
                        'error': None
                    })

            return results, None

    @staticmethod
    def analyze_code(code):
        """Анализ кода: подсчет функций и классов"""
        functions_count = 0
        classes_count = 0

        try:
            tree = ast.parse(code)

            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    functions_count += 1
                elif isinstance(node, ast.ClassDef):
                    classes_count += 1

        except:
            pass

        return functions_count, classes_count


@csrf_exempt
@require_POST
def run_code(request):
    """Обработчик выполнения кода с обработкой ошибок JSON"""
    try:
        data = request.POST
        code = data.get('code', '').strip()
        tab_id = data.get('tab_id')
        language = data.get('language', 'python')

        if not code:
            return JsonResponse({
                'success': False,
                'error': 'Код не может быть пустым'
            })

        # Запоминаем время начала
        start_time = time.time()

        # Проверка безопасности кода
        is_safe, message = CodeSecurityChecker.check_code_security(code)
        if not is_safe:
            return JsonResponse({
                'success': False,
                'error': f'Код не прошел проверку безопасности: {message}'
            })

        # Выполнение кода
        line_results, final_output = SafeCodeRunner.execute_code(code)

        # Анализ кода
        functions_count, classes_count = SafeCodeRunner.analyze_code(code)

        # Подсчитываем статистику
        total_lines = len(line_results)
        successful_lines = sum(1 for r in line_results if r['success'])
        error_lines = sum(1 for r in line_results if not r['success'])

        # Время выполнения
        execution_time = int((time.time() - start_time) * 1000)  # в миллисекундах

        # Формируем сводку
        execution_summary = {
            'execution_time': execution_time,
            'total_lines': total_lines,
            'successful_lines': successful_lines,
            'error_lines': error_lines,
            'functions_count': functions_count,
            'classes_count': classes_count
        }

        # Фильтруем вывод (убираем пустые строки)
        filtered_line_results = []
        for result in line_results:
            # Оставляем только строки с выводом или ошибками
            if (result.get('output') and result['output'].strip()) or not result['success']:
                filtered_line_results.append({
                    'line': result['line'],
                    'code': result['code'][:100] + ('...' if len(result['code']) > 100 else ''),
                    'output': result.get('output', ''),
                    'success': result['success'],
                    'error': result.get('error')
                })

        return JsonResponse({
            'success': True,
            'tab_id': tab_id,
            'execution_summary': execution_summary,
            'line_results': filtered_line_results,
            'functions_count': functions_count,
            'classes_count': classes_count,
            'final_output': final_output if final_output else None,
            'execution_time_ms': execution_time
        })

    except Exception as e:
        import traceback
        traceback_str = traceback.format_exc()
        print(f"Ошибка в run_code: {str(e)}")
        print(f"Traceback: {traceback_str}")

        return JsonResponse({
            'success': False,
            'error': f'Ошибка сервера: {str(e)}'
        })