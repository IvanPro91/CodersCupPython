import collections
import datetime
import json
import math
import random
import re

from celery import shared_task
from celery.exceptions import SoftTimeLimitExceeded
import time
import ast
from io import StringIO


@shared_task(name='execute_user_code')
def execute_user_code(code):
    output_buffer = StringIO()
    start_time = time.perf_counter()

    # Список разрешенных библиотек
    ALLOWED_MODULES = {
        'math': math,
        'random': random,
        'datetime': datetime,
        'json': json,
        'collections': collections,
        're': re,
        'time': time,  # Полезно для замеров внутри кода
    }

    def safe_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name in ALLOWED_MODULES:
            return ALLOWED_MODULES[name]
        raise ImportError(f"Импорт модуля '{name}' запрещен в целях безопасности.")

    safe_builtins = {
        '__build_class__': __build_class__,
        '__import__': safe_import,  # Подменяем стандартный импорт
        'object': object,
        'type': type,
        'print': lambda *args, **kwargs: print(*args, file=output_buffer, **kwargs),
        'range': range, 'len': len, 'int': int, 'str': str, 'float': float,
        'list': list, 'dict': dict, 'tuple': tuple, 'set': set, 'bool': bool,
        'sum': sum, 'min': min, 'max': max, 'abs': abs, 'enumerate': enumerate, 'zip': zip,
        'property': property, 'staticmethod': staticmethod, 'classmethod': classmethod,
        'Exception': Exception, 'StopIteration': StopIteration,
    }

    exec_scope = {
        "__builtins__": safe_builtins,
        "__name__": "__main__",
    }

    try:
        compiled_code = compile(code, '<user_code>', 'exec')
        exec(compiled_code, exec_scope)

        execution_time = round((time.perf_counter() - start_time) * 1000, 2)

        # Статистика (AST)
        tree = ast.parse(code)
        func_count = sum(1 for n in ast.walk(tree) if isinstance(n, ast.FunctionDef))
        class_count = sum(1 for n in ast.walk(tree) if isinstance(n, ast.ClassDef))

        return {
            'success': True,
            'output': output_buffer.getvalue(),
            'execution_time_ms': execution_time,
            'stats': {
                'functions': func_count,
                'classes': class_count,
                'lines': len(code.splitlines())
            }
        }

    except SoftTimeLimitExceeded:
        return {
            'success': False,
            'error': 'Превышен лимит времени выполнения (10 сек.)',
            'output': output_buffer.getvalue()
        }
    except Exception as e:
        return {
            'success': False,
            'error': f"{type(e).__name__}: {str(e)}",
            'output': output_buffer.getvalue()
        }