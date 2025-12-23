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
    type_ = models.CharField(max_length=20, choices=TYPE_CHOICES)
    name = models.CharField(max_length=20)
    code = models.TextField()
    invited_username = models.CharField(max_length=20, null=True, blank=True)
    task_type = models.CharField(max_length=20, null=True, blank=True)
