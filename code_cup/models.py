import uuid
from uuid import uuid4

from asgiref.sync import sync_to_async
from django.db import models
from django.utils.translation import gettext_lazy as _

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
    """Модель задачи"""

    class Difficulty(models.TextChoices):
        EASY = 'easy', _('Легкий')
        MEDIUM = 'medium', _('Средний')
        HARD = 'hard', _('Сложный')
        EXPERT = 'expert', _('Экспертный')

    # Основные поля
    id = models.CharField(
        max_length=50,
        primary_key=True,
        verbose_name=_('ID задачи')
    )

    share_token = models.UUIDField(
        verbose_name=_('Токен для доступа'),
        default=uuid.uuid4,
        editable=False,
        unique=True,
        help_text=_('Уникальный токен для предоставления доступа к задаче')
    )

    is_public = models.BooleanField(
        verbose_name=_('Публичная задача'),
        default=False,
        help_text=_('Доступна ли задача всем по токену')
    )

    title = models.CharField(
        max_length=255,
        verbose_name=_('Название задачи')
    )

    description = models.TextField(
        verbose_name=_('Описание'),
        blank=True
    )

    code = models.TextField(
        verbose_name=_('Исходный код')
    )

    difficulty = models.CharField(
        max_length=20,
        choices=Difficulty.choices,
        default=Difficulty.MEDIUM,
        verbose_name=_('Сложность')
    )

    created = models.DateTimeField(
        verbose_name=_('Дата создания'),
        auto_now_add=True
    )

    # Связанные поля (создаются отдельными моделями)

    class Meta:
        verbose_name = _('Задача')
        verbose_name_plural = _('Задачи')
        ordering = ['-created']
        indexes = [
            models.Index(fields=['share_token']),
            models.Index(fields=['is_public']),
            models.Index(fields=['difficulty']),
        ]

    def __str__(self):
        return f"{self.title} ({self.id})"

    def generate_new_token(self):
        """Сгенерировать новый токен доступа"""
        self.share_token = uuid.uuid4()
        self.save()
        return self.share_token

    def get_share_url(self, request=None):
        """Получить URL для доступа к задаче"""
        from django.urls import reverse
        url = reverse('task-by-token', kwargs={'token': self.share_token})
        if request:
            return request.build_absolute_uri(url)
        return url


class TaskConstraints(models.Model):
    """Модель ограничений задачи"""

    task = models.OneToOneField(
        Task,
        on_delete=models.CASCADE,
        related_name='constraints',
        verbose_name=_('Задача'),
        primary_key=False
    )

    max_lines = models.PositiveIntegerField(
        verbose_name=_('Максимум строк'),
        default=50
    )

    max_line_length = models.PositiveIntegerField(
        verbose_name=_('Максимальная длина строки'),
        default=80
    )

    max_chars = models.PositiveIntegerField(
        verbose_name=_('Максимум символов'),
        default=1000
    )

    max_functions = models.PositiveIntegerField(
        verbose_name=_('Максимум функций'),
        default=5
    )

    max_classes = models.PositiveIntegerField(
        verbose_name=_('Максимум классов'),
        default=3
    )

    class Meta:
        verbose_name = _('Ограничение задачи')
        verbose_name_plural = _('Ограничения задач')

    def __str__(self):
        return f"Ограничения для {self.task.title}"


class ForbiddenWord(models.Model):
    """Модель запрещенного слова"""

    task = models.ForeignKey(
        Task,
        on_delete=models.CASCADE,
        related_name='forbidden_words',
        verbose_name=_('Задача')
    )

    word = models.CharField(
        max_length=100,
        verbose_name=_('Запрещенное слово')
    )

    class Meta:
        verbose_name = _('Запрещенное слово')
        verbose_name_plural = _('Запрещенные слова')
        unique_together = ['task', 'word']
        ordering = ['word']

    def __str__(self):
        return f"{self.word} (для {self.task.title})"


class Example(models.Model):
    """Модель примера ввода/вывода"""

    task = models.ForeignKey(
        Task,
        on_delete=models.CASCADE,
        related_name='examples',
        verbose_name=_('Задача')
    )

    input_data = models.JSONField(
        verbose_name=_('Входные данные'),
        default=dict,
        help_text=_('Данные на вход в формате JSON')
    )

    output_data = models.JSONField(
        verbose_name=_('Выходные данные'),
        default=dict,
        help_text=_('Ожидаемый результат в формате JSON')
    )

    order = models.PositiveIntegerField(
        verbose_name=_('Порядок'),
        default=0,
        help_text=_('Порядок отображения примеров')
    )

    class Meta:
        verbose_name = _('Пример')
        verbose_name_plural = _('Примеры')
        ordering = ['order']

    def __str__(self):
        return f"Пример {self.order} для {self.task.title}"


class Tag(models.Model):
    """Модель тега"""

    name = models.CharField(
        max_length=50,
        unique=True,
        verbose_name=_('Название тега'),
        help_text=_('Уникальное название тега')
    )

    tasks = models.ManyToManyField(
        Task,
        related_name='tags',
        verbose_name=_('Задачи'),
        blank=True
    )

    created = models.DateTimeField(
        verbose_name=_('Дата создания'),
        auto_now_add=True
    )

    class Meta:
        verbose_name = _('Тег')
        verbose_name_plural = _('Теги')
        ordering = ['name']

    def __str__(self):
        return self.name


class TaskStats(models.Model):
    """Модель статистики задачи"""

    task = models.OneToOneField(
        Task,
        on_delete=models.CASCADE,
        related_name='stats',
        verbose_name=_('Задача'),
        primary_key=False
    )

    lines = models.PositiveIntegerField(
        verbose_name=_('Количество строк'),
        default=0
    )

    chars = models.PositiveIntegerField(
        verbose_name=_('Количество символов'),
        default=0
    )

    non_space_chars = models.PositiveIntegerField(
        verbose_name=_('Символов без пробелов'),
        default=0
    )

    functions = models.PositiveIntegerField(
        verbose_name=_('Количество функций'),
        default=0
    )

    classes = models.PositiveIntegerField(
        verbose_name=_('Количество классов'),
        default=0
    )

    analyzed_at = models.DateTimeField(
        verbose_name=_('Время анализа'),
        auto_now=True
    )

    class Meta:
        verbose_name = _('Статистика задачи')
        verbose_name_plural = _('Статистики задач')

    def __str__(self):
        return f"Статистика для {self.task.title}"


class TaskAccessLog(models.Model):
    """Модель лога доступа к задаче"""

    task = models.ForeignKey(
        Task,
        on_delete=models.CASCADE,
        related_name='access_logs',
        verbose_name=_('Задача')
    )

    accessed_at = models.DateTimeField(
        verbose_name=_('Время доступа'),
        auto_now_add=True
    )

    ip_address = models.GenericIPAddressField(
        verbose_name=_('IP адрес'),
        null=True,
        blank=True
    )

    user_agent = models.TextField(
        verbose_name=_('User Agent'),
        blank=True
    )

    referer = models.URLField(
        verbose_name=_('Источник перехода'),
        blank=True,
        null=True
    )

    class Meta:
        verbose_name = _('Лог доступа к задаче')
        verbose_name_plural = _('Логи доступа к задачам')
        ordering = ['-accessed_at']
        indexes = [
            models.Index(fields=['accessed_at']),
            models.Index(fields=['ip_address']),
        ]

    def __str__(self):
        return f"Доступ к {self.task.title} в {self.accessed_at}"
