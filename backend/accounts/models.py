from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    ROLE_ADMIN = "admin"
    ROLE_GROWER = "grower"
    ROLE_CHOICES = [
        (ROLE_ADMIN, "管理员"),
        (ROLE_GROWER, "种植员"),
    ]

    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default=ROLE_GROWER)

    def __str__(self):
        return f"{self.username} ({self.role})"
