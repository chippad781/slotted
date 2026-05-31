from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    """
    Custom user — we use email for login but keep username as the
    public handle that shows up in the booking URL (e.g. /amogh).
    Always do a custom user model at the start of a Django project,
    even if you don't need it yet. Adding one later is painful.
    """
    email = models.EmailField(unique=True)
    timezone = models.CharField(max_length=64, default='UTC')
    display_name = models.CharField(max_length=120, blank=True)
    bio = models.TextField(blank=True)

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username']

    def __str__(self):
        return self.email
