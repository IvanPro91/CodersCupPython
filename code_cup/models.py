import json
from uuid import uuid4

from asgiref.sync import sync_to_async
from django.db import models

from user.models import User


class UserTabs(models.Model):
    """choice"""

    SINGLE = "single"
    DUEL = "duel"
    COLLABORATIVE = "collaborative"

    TYPE_CHOICES = (
        (SINGLE, "single"),
        (DUEL, "duel"),
        (COLLABORATIVE, "collaborative"),
    )
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    type_tab = models.CharField(max_length=20, choices=TYPE_CHOICES)
    name = models.CharField(max_length=20)
    code = models.TextField()
    href = models.TextField(default="")
    uuid = models.TextField(default="", unique=True)
    is_view = models.BooleanField(default=True)
    invited_username = models.CharField(max_length=20, null=True, blank=True)
    task_type = models.CharField(max_length=20, null=True, blank=True)

    @sync_to_async
    def filter(self, type_tab, user, name):
        return UserTabs.objects.filter(
            type_tab=type_tab, user=user, name=name
        ).first()

    @sync_to_async
    def set_not_view(self, user, tab_id):
        tab = UserTabs.objects.filter(pk=tab_id, user=user).first()
        tab.is_view = False
        tab.save()

    @sync_to_async
    def add(self, user, type_tab, name, code, invited_username=None, task_type=None):
        uuid = f"{name}:{uuid4()}"
        obj, created = UserTabs.objects.get_or_create(
            user=user, type_tab=type_tab, name=name, code=code, uuid=uuid,
            invited_username=invited_username, task_type=task_type
        )
        return obj.to_dict()

    @sync_to_async
    def get_tabs(self, user, pk=None) -> list[dict]:
        filter_data = {"user": user, "pk": pk} if pk else {"user": user}
        filter_data['is_view'] = True
        all_data = UserTabs.objects.filter(**filter_data).all()
        to_dict = [data.to_dict() for data in all_data]
        return to_dict

    def to_dict(self):
        return {
            "type_tab": self.type_tab,
            "name": self.name,
            "pk": self.pk,
            "href": self.href,
            "invited_username": self.invited_username,
            "task_type": self.task_type
        }


class Task(models.Model):
    LEVEL_CHOICES = [
        ('junior', 'Начинающий'),
        ('middle', 'Средний'),
        ('hard', 'Сложный'),
        ('expert', 'Эксперт'),
    ]

    CATEGORY_CHOICES = [
        ('algorithm', 'Алгоритмы'),
        ('string', 'Строки'),
        ('array', 'Массивы'),
        ('math', 'Математика'),
        ('logic', 'Логика'),
        ('dynamic', 'Динамическое программирование'),
        ('graph', 'Графы'),
        ('holiday', 'Праздничные'),
        ('google', 'Google'),
        ('yandex', 'Yandex'),
        ('other', 'Другое'),
    ]

    num = models.CharField(max_length=20, verbose_name="Номер задачи")
    name = models.CharField(max_length=255, verbose_name="Название задачи")
    code = models.TextField(verbose_name="Шаблон кода")
    level = models.CharField(max_length=20, choices=LEVEL_CHOICES, verbose_name="Уровень сложности")
    task_text = models.TextField(verbose_name="Текст задачи")

    # JSON поля как TextField с валидацией
    exclude_json = models.TextField(
        default='[]',
        verbose_name="Запрещенные импорты",
        help_text="JSON список запрещенных импортов"
    )
    hints_json = models.TextField(
        default='{}',
        verbose_name="Подсказки",
        help_text="JSON словарь {секунды: текст_подсказки}"
    )
    test_code_json = models.TextField(
        default='[]',
        verbose_name="Тесты",
        help_text="JSON список строк с тестами"
    )
    tags_json = models.TextField(
        default='[]',
        verbose_name="Теги",
        help_text="JSON список тегов"
    )

    category = models.CharField(
        max_length=100,
        choices=CATEGORY_CHOICES,
        default='algorithm',
        verbose_name="Категория"
    )

    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата создания")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Дата обновления")
    is_active = models.BooleanField(default=True, verbose_name="Активна")
    time_limit = models.IntegerField(default=2, verbose_name="Ограничение времени (сек)")
    memory_limit = models.IntegerField(default=256, verbose_name="Ограничение памяти (МБ)")

    class Meta:
        verbose_name = "Задача"
        verbose_name_plural = "Задачи"
        ordering = ['num']
        indexes = [
            models.Index(fields=['level']),
            models.Index(fields=['category']),
            models.Index(fields=['is_active']),
        ]

    def __str__(self):
        return f"{self.num}: {self.name} ({self.get_level_display()})"

    # Свойства для удобного доступа
    @property
    def exclude(self):
        try:
            return json.loads(self.exclude_json)
        except (json.JSONDecodeError, TypeError):
            return []

    @exclude.setter
    def exclude(self, value):
        self.exclude_json = json.dumps(value, ensure_ascii=False)

    @property
    def hints(self):
        try:
            return json.loads(self.hints_json)
        except (json.JSONDecodeError, TypeError):
            return {}

    @hints.setter
    def hints(self, value):
        self.hints_json = json.dumps(value, ensure_ascii=False)

    @property
    def test_code(self):
        try:
            return json.loads(self.test_code_json)
        except (json.JSONDecodeError, TypeError):
            return []

    @test_code.setter
    def test_code(self, value):
        self.test_code_json = json.dumps(value, ensure_ascii=False)

    @property
    def tags(self):
        try:
            return json.loads(self.tags_json)
        except (json.JSONDecodeError, TypeError):
            return []

    @tags.setter
    def tags(self, value):
        self.tags_json = json.dumps(value, ensure_ascii=False)

    def clean(self):
        """Валидация JSON полей перед сохранением"""
        from django.core.exceptions import ValidationError

        try:
            json.loads(self.exclude_json)
        except json.JSONDecodeError:
            raise ValidationError({'exclude_json': 'Некорректный JSON'})

        try:
            json.loads(self.hints_json)
        except json.JSONDecodeError:
            raise ValidationError({'hints_json': 'Некорректный JSON'})

        try:
            json.loads(self.test_code_json)
        except json.JSONDecodeError:
            raise ValidationError({'test_code_json': 'Некорректный JSON'})

        try:
            json.loads(self.tags_json)
        except json.JSONDecodeError:
            raise ValidationError({'tags_json': 'Некорректный JSON'})

    def save(self, *args, **kwargs):
        # Убедимся, что JSON поля корректны
        if not self.exclude_json or self.exclude_json.strip() == '':
            self.exclude_json = '[]'
        if not self.hints_json or self.hints_json.strip() == '':
            self.hints_json = '{}'
        if not self.test_code_json or self.test_code_json.strip() == '':
            self.test_code_json = '[]'
        if not self.tags_json or self.tags_json.strip() == '':
            self.tags_json = '[]'

        self.full_clean()  # Вызываем валидацию
        super().save(*args, **kwargs)

    def get_formatted_task_text(self):
        """Возвращает текст задачи с HTML разметкой"""
        import re
        text = self.task_text

        # Заменяем переносы строк на <br>
        text = text.replace('\n', '<br>')

        # Форматирование примеров
        text = re.sub(r'Примеры?:<br>(.*?)(?=<br>|$)',
                      r'<strong>Примеры:</strong><br>\1',
                      text, flags=re.DOTALL)

        return text


class TaskTestCase(models.Model):
    """Отдельная таблица для тестов"""
    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name='test_cases')
    test_name = models.CharField(max_length=200, verbose_name="Название теста")
    test_code = models.TextField(verbose_name="Код теста")
    is_hidden = models.BooleanField(default=False, verbose_name="Скрытый тест")
    order = models.IntegerField(default=0, verbose_name="Порядок")

    class Meta:
        verbose_name = "Тестовый случай"
        verbose_name_plural = "Тестовые случаи"
        ordering = ['order', 'id']
        unique_together = ['task', 'test_name']

    def __str__(self):
        return f"{self.task.num}: {self.test_name}"


class TaskHint(models.Model):
    """Отдельная таблица для подсказок"""
    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name='task_hints')
    seconds = models.IntegerField(verbose_name="Через сколько секунд показать")
    text = models.TextField(verbose_name="Текст подсказки")
    order = models.IntegerField(default=0, verbose_name="Порядок")

    class Meta:
        verbose_name = "Подсказка"
        verbose_name_plural = "Подсказки"
        ordering = ['seconds', 'order']
        unique_together = ['task', 'seconds']

    def __str__(self):
        return f"Подсказка через {self.seconds}с"

    def formatted_text(self):
        """Возвращает текст с HTML разметкой"""
        return self.text.replace('\n', '<br>')


class UserSolution(models.Model):
    """Модель для хранения решений пользователей"""
    STATUS_CHOICES = [
        ('pending', 'На проверке'),
        ('passed', 'Пройдено'),
        ('failed', 'Не пройдено'),
        ('error', 'Ошибка'),
        ('timeout', 'Превышено время'),
    ]

    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name='solutions')
    user_id = models.IntegerField(verbose_name="ID пользователя")
    user_code = models.TextField(verbose_name="Код пользователя")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    passed_tests = models.IntegerField(default=0, verbose_name="Пройдено тестов")
    total_tests = models.IntegerField(default=0, verbose_name="Всего тестов")
    execution_time = models.FloatField(null=True, blank=True, verbose_name="Время выполнения (сек)")
    memory_used = models.IntegerField(null=True, blank=True, verbose_name="Использовано памяти (КБ)")
    error_message = models.TextField(blank=True, verbose_name="Сообщение об ошибке")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата отправки")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Дата обновления")

    class Meta:
        verbose_name = "Решение пользователя"
        verbose_name_plural = "Решения пользователей"
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user_id']),
            models.Index(fields=['task']),
            models.Index(fields=['status']),
            models.Index(fields=['created_at']),
        ]

    def __str__(self):
        return f"{self.user_id} - {self.task.num} - {self.get_status_display()}"

    @property
    def success_rate(self):
        """Процент успешных тестов"""
        if self.total_tests > 0:
            return round((self.passed_tests / self.total_tests) * 100, 2)
        return 0

    @property
    def is_successful(self):
        """Пройдены ли все тесты"""
        return self.status == 'passed' and self.passed_tests == self.total_tests

    def run_tests(self):
        """Запуск тестов для решения (заглушка, реализуйте по необходимости)"""
        # Здесь будет логика запуска тестов
        # Например, использование exec() или отдельного процесса
        pass