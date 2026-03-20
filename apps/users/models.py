import uuid
from django.contrib.auth.models import AbstractUser
from django.db import models

class User(AbstractUser):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(unique=True)
    is_system = models.BooleanField(default=False)
    
    # We keep username as the USERNAME_FIELD, which is the default for AbstractUser.
    # No need to override USERNAME_FIELD or REQUIRED_FIELDS or the Manager since
    # the default Django auth system behavior perfectly matches our requirements.

    def __str__(self):
        return self.username
