import re
import tempfile
import os
import time
import subprocess
import json
import shutil
from celery import shared_task


def clean_user_output(text):
    """Очищает стандартный вывод пользователя (print) от технических путей."""
    if not text: return ""
    # Удаляем пути к временным папкам
    text = re.sub(r'[A-Z]:\\.*\\Temp\\tmp[a-z0-9_]+', '[system]', text)
    text = re.sub(r'/tmp/tmp[a-z0-9_]+', '[system]', text)
    return text.strip()[:2000]


@shared_task(name='execute_user_code')
def execute_user_code(task_id: int, user_code: str):
    """
    Выполняет код пользователя и возвращает только статус прохождения.
    Тестовые данные и ассерты скрыты от пользователя.
    """
    temp_dir = tempfile.mkdtemp()
    user_file = os.path.join(temp_dir, "solution.py")
    test_file = os.path.join(temp_dir, "test_solution.py")
    report_file = os.path.join(temp_dir, "report.json")

    try:
        from code_cup.models import Task
        task = Task.objects.get(id=task_id)

        # 1. Записываем код пользователя
        with open(user_file, 'w', encoding='utf-8') as f:
            f.write(user_code)

        # 2. Генерируем файл тестов (изолируем каждый тест в функцию)
        test_lines = task.test_code
        with open(test_file, 'w', encoding='utf-8') as f:
            f.write("import pytest\nfrom solution import *\n\n")
            for i, line in enumerate(test_lines):
                if not line.strip(): continue
                # Оборачиваем каждый тест в функцию, чтобы pytest мог их посчитать отдельно
                f.write(f"def test_case_{i}():\n")
                # Если в базе лежит 'def test...', выполняем только вызов, если просто 'assert...', пишем его
                if line.strip().startswith('def '):
                    # Извлекаем только имя функции и вызов из строки типа "def test_x(): assert f()==1"
                    match = re.search(r'assert\s+(.*)', line)
                    content = match.group(0) if match else "pass"
                    f.write(f"    {content}\n\n")
                else:
                    f.write(f"    {line.strip()}\n\n")

        # 3. Запускаем pytest с минимальным выводом
        start_time = time.time()
        cmd = [
            'pytest',
            test_file,
            '--json-report',
            f'--json-report-file={report_file}',
            '--tb=no',  # Скрываем детали ошибок (traceback)
            '--no-header',  # Убираем заголовок pytest
            '--capture=sys'  # Перехватываем только системный вывод
        ]

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=task.time_limit,
            cwd=temp_dir
        )
        execution_time = round((time.time() - start_time) * 1000, 2)

        # 4. Обработка результатов из JSON
        test_details = []
        passed_count = 0

        if os.path.exists(report_file):
            with open(report_file, 'r') as f:
                report_data = json.load(f)

            # Собираем данные по каждому тесту
            for test_result in report_data.get('tests', []):
                status = test_result.get('outcome')

                # Формируем безопасное сообщение об ошибке
                if status == 'passed':
                    passed_count += 1
                    msg = "Тест пройден"
                else:
                    # Проверяем, не вызвана ли ошибка отсутствием функции
                    long_msg = test_result.get('call', {}).get('crash', {}).get('message', '')
                    if "is not defined" in long_msg:
                        msg = "Ошибка: Функция не найдена. Проверьте название функции в задании."
                    elif "SyntaxError" in long_msg:
                        msg = "Ошибка: Синтаксическая ошибка в коде."
                    else:
                        msg = "Ошибка: Неверный результат"  # Скрываем, какой именно результат

                test_details.append({
                    'name': f"Тест №{len(test_details) + 1}",
                    'status': status,
                    'message': msg
                })
        else:
            # Если файл отчета не создался, значит код пользователя вообще не запустился
            return {
                'success': False,
                'error': "Критическая ошибка при запуске. Проверьте синтаксис кода.",
                'status': 'error'
            }

        total_tests = len(test_details)
        all_passed = (passed_count == total_tests) and total_tests > 0

        # Формируем финальный ответ
        return {
            'success': True,
            'passed': all_passed,
            'status': 'passed' if all_passed else 'failed',
            'execution_time_ms': execution_time,
            'stats': {
                'passed_tests': passed_count,
                'total_tests': total_tests,
                'success_rate': round(passed_count / total_tests * 100, 2) if total_tests > 0 else 0
            },
            'test_details': test_details,
            #'user_print': clean_user_output(result.stdout)  # Показываем только то, что пользователь напечатал сам
        }

    except subprocess.TimeoutExpired:
        return {'success': False, 'error': f'Лимит времени ({task.time_limit} сек.) превышен', 'status': 'timeout'}
    except Exception as e:
        return {'success': False, 'error': "Внутренняя ошибка сервера при проверке", 'status': 'error'}
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)