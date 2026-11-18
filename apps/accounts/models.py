import uuid

from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(unique=True)
    phone_number = models.CharField(max_length=30, blank=True)
    email_verified = models.BooleanField(default=False)
    phone_verified = models.BooleanField(default=False)
    preferred_language = models.CharField(max_length=12, default="en")
    timezone = models.CharField(max_length=64, default="Asia/Kathmandu")
    profile_photo = models.ImageField(upload_to="users/profiles/", blank=True, null=True)

    def __str__(self) -> str:
        return self.email or self.username
