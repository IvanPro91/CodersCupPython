import ast
import multiprocessing
import time
from io import StringIO

# Константы безопасности
FORBIDDEN_COMMANDS = {'eval', 'exec', '__import__', 'open', 'compile', 'globals', 'locals'}
FORBIDDEN_MODULES = {'os', 'sys', 'subprocess', 'shutil', 'socket', 'requests'}

class CodeSecurityChecker:
    @staticmethod
    def check_code_security(code):
        try:
            tree = ast.parse(code)
            for node in ast.walk(tree):
                # Проверка импортов
                if isinstance(node, (ast.Import, ast.ImportFrom)):
                    modules = [alias.name for alias in node.names] if isinstance(node, ast.Import) else [node.module]
                    for m in modules:
                        if m in FORBIDDEN_MODULES or any(m.startswith(f"{fm}.") for fm in FORBIDDEN_MODULES):
                            return False, f"Доступ к модулю '{m}' запрещен"

                # Проверка вызовов функций и атрибутов
                if isinstance(node, ast.Call):
                    func_name = ""
                    if isinstance(node.func, ast.Name):
                        func_name = node.func.id
                    elif isinstance(node.func, ast.Attribute):
                        func_name = node.func.attr

                    if func_name in FORBIDDEN_COMMANDS:
                        return False, f"Использование функции/метода '{func_name}' запрещено"

            return True, "OK"
        except SyntaxError as e:
            return False, f"Ошибка синтаксиса: {str(e)}"


def internal_worker(code, result_dict):
    """Функция, работающая внутри изолированного процесса"""
    output_buffer = StringIO()

    # Создаем максимально ограниченный scope
    safe_builtins = {
        '__build_class__': __build_class__,
        'print': lambda *args, **kwargs: print(*args, file=output_buffer, **kwargs),
        'range': range, 'len': len, 'int': int, 'str': str, 'float': float,
        'list': list, 'dict': dict, 'tuple': tuple, 'set': set, 'bool': bool,
        'sum': sum, 'min': min, 'max': max, 'abs': abs, 'enumerate': enumerate, 'zip': zip
    }

    global_vars = {"__builtins__": safe_builtins}

    try:
        start_time = time.perf_counter()
        # Выполнение кода
        exec(code, global_vars)
        end_time = time.perf_counter()

        result_dict['success'] = True
        result_dict['output'] = output_buffer.getvalue()
        result_dict['time'] = round((end_time - start_time) * 1000, 2)
    except Exception as e:
        print(code, e)
        result_dict['success'] = False
        result_dict['error'] = f"{type(e).__name__}: {str(e)}"
        result_dict['output'] = output_buffer.getvalue()


class SafeCodeRunner:
    @staticmethod
    def run_with_timeout(code, timeout=10):
        # На Windows важно использовать Manager или очереди для обмена данными
        with multiprocessing.Manager() as manager:
            result_dict = manager.dict()

            # Создаем процесс
            process = multiprocessing.Process(
                target=internal_worker,
                args=(code, result_dict)
            )
            process.start()
            process.join(timeout)

            if process.is_alive():
                process.terminate()
                return {
                    'success': False,
                    'error': 'Timeout',
                    'output': 'Превышено время выполнения (10 сек)'
                }

            # Копируем данные из прокси-объекта в обычный словарь
            return dict(result_dict)
