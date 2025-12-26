import json
import os
import sys
from django.core.management.base import BaseCommand
from django.db import transaction
from code_cup.models import Task, TaskTestCase, TaskHint


class Command(BaseCommand):
    help = 'Импорт задач из JSON файла в базу данных'

    def add_arguments(self, parser):
        parser.add_argument(
            'json_file',
            type=str,
            help='Путь к JSON файлу с задачами'
        )
        parser.add_argument(
            '--update',
            action='store_true',
            help='Обновить существующие задачи'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Показать что будет импортировано без сохранения'
        )
        parser.add_argument(
            '--category',
            type=str,
            default='',
            help='Категория для импортируемых задач'
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Принудительно импортировать, даже если задача уже существует'
        )

    def handle(self, *args, **options):
        self.json_file = options['json_file']
        self.update_existing = options['update']
        self.dry_run = options['dry_run']
        self.category = options['category']
        self.force = options['force']

        if not os.path.exists(self.json_file):
            self.stderr.write(self.style.ERROR(f'Файл не найден: {self.json_file}'))
            sys.exit(1)

        try:
            with open(self.json_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except json.JSONDecodeError as e:
            self.stderr.write(self.style.ERROR(f'Ошибка парсинга JSON: {e}'))
            sys.exit(1)

        # Обрабатываем как массив задач, так и одну задачу
        if isinstance(data, dict):
            tasks_data = [data]
        elif isinstance(data, list):
            tasks_data = data
        else:
            self.stderr.write(self.style.ERROR('Неверный формат JSON'))
            sys.exit(1)

        self.stdout.write(f'Найдено {len(tasks_data)} задач')

        results = {
            'imported': 0,
            'updated': 0,
            'skipped': 0,
            'errors': 0
        }

        for i, task_data in enumerate(tasks_data, 1):
            try:
                result = self.process_single_task(task_data, i)
                results[result] += 1
            except Exception as e:
                results['errors'] += 1
                self.stderr.write(self.style.ERROR(f'Ошибка в задаче {i}: {e}'))

        self.print_summary(results)

    def process_single_task(self, task_data, index):
        """Обработка одной задачи"""
        task_num = task_data.get('num', f'auto_{index}')
        task_name = task_data.get('name', f'Задача {task_num}')

        self.stdout.write(f'[{index}] Обработка: {task_num} - {task_name}')

        # Проверяем существование
        try:
            existing_task = Task.objects.get(name=task_name)
            if existing_task and not self.update_existing and not self.force:
                self.stdout.write(self.style.WARNING(f'  Задача уже существует, пропускаем'))
                return 'skipped'
            task = existing_task
            is_new = False
        except Task.DoesNotExist:
            task = Task(num=task_num)
            is_new = True

        # Валидация данных
        if not self.validate_task_data(task_data):
            raise ValueError('Некорректные данные задачи')

        # Подготовка данных
        task.name = task_data.get('name', '')
        task.code = task_data.get('code', '')
        task.level = task_data.get('level', 'junior')
        task.task_text = task_data.get('task_text', '')
        task.category = self.category or task_data.get('category', 'algorithm')

        # JSON поля через свойства
        task.exclude = task_data.get('exclude', [])
        task.hints = task_data.get('hints', {})
        task.test_code = task_data.get('test_code', [])

        # Автоматические теги
        tags = task_data.get('tags', [])
        if task.level not in tags:
            tags.append(task.level)
        if task.category not in tags:
            tags.append(task.category)
        task.tags = list(set(tags))  # Убираем дубликаты

        # Сухой прогон
        if self.dry_run:
            self.print_task_info(task, is_new)
            return 'imported' if is_new else 'updated'

        # Сохранение
        try:
            with transaction.atomic():
                task.save()

                # Создаем связанные объекты (опционально)
                if is_new or self.update_existing:
                    self.create_related_objects(task, task_data)

                action = 'импортирована' if is_new else 'обновлена'
                self.stdout.write(self.style.SUCCESS(f'  ✓ Задача {action}'))

                return 'imported' if is_new else 'updated'

        except Exception as e:
            raise ValueError(f'Ошибка сохранения: {e}')

    def validate_task_data(self, task_data):
        """Валидация данных задачи"""
        required_fields = ['num', 'name', 'code', 'task_text']
        for field in required_fields:
            if field not in task_data or not task_data[field]:
                raise ValueError(f'Отсутствует обязательное поле: {field}')

        # Проверяем JSON поля
        json_fields = ['exclude', 'hints', 'test_code', 'tags']
        for field in json_fields:
            if field in task_data:
                try:
                    # Преобразуем в строку и обратно для проверки
                    json.dumps(task_data[field])
                except (TypeError, ValueError):
                    raise ValueError(f'Некорректный JSON в поле {field}')

        return True

    def print_task_info(self, task, is_new):
        """Вывод информации о задаче для сухого прогона"""
        status = 'НОВАЯ' if is_new else 'СУЩЕСТВУЮЩАЯ'
        self.stdout.write(f'  Статус: {status}')
        self.stdout.write(f'  Уровень: {task.level}')
        self.stdout.write(f'  Категория: {task.category}')
        self.stdout.write(f'  Теги: {", ".join(task.tags)}')
        self.stdout.write(f'  Тестов: {len(task.test_code)}')
        self.stdout.write(f'  Подсказок: {len(task.hints)}')
        self.stdout.write(f'  Запрещенные импорты: {", ".join(task.exclude)}')
        self.stdout.write('')

    def create_related_objects(self, task, task_data):
        """Создание связанных объектов (тесты и подсказки в отдельных таблицах)"""
        # Очищаем старые связанные объекты
        task.test_cases.all().delete()
        task.task_hints.all().delete()

        # Создаем тестовые случаи
        test_code = task.test_code
        for i, test in enumerate(test_code, 1):
            TaskTestCase.objects.create(
                task=task,
                test_name=f'test_{i}',
                test_code=test,
                order=i
            )

        # Создаем подсказки
        hints = task.hints
        for i, (seconds, text) in enumerate(hints.items(), 1):
            try:
                seconds_int = int(seconds)
                TaskHint.objects.create(
                    task=task,
                    seconds=seconds_int,
                    text=text,
                    order=i
                )
            except (ValueError, TypeError):
                continue

    def print_summary(self, results):
        """Вывод сводки импорта"""
        self.stdout.write('\n' + '=' * 50)
        self.stdout.write(self.style.SUCCESS('ИТОГИ ИМПОРТА:'))
        self.stdout.write(f'Импортировано: {results["imported"]}')
        self.stdout.write(f'Обновлено: {results["updated"]}')
        self.stdout.write(f'Пропущено: {results["skipped"]}')
        self.stdout.write(f'Ошибок: {results["errors"]}')

        if self.dry_run:
            self.stdout.write(self.style.WARNING('\nРЕЖИМ ПРОСМОТРА - изменения не сохранены'))