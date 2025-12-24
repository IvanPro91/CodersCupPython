from asgiref.sync import sync_to_async
from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    """
    User model
    """

    token = models.CharField(max_length=255, null=True, blank=True, unique=True)
    create_at = models.DateTimeField(auto_now_add=True)
    update_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)

    @sync_to_async
    def get_user(self, pk):
        return User.objects.filter(pk=pk).first()