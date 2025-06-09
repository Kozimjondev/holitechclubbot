from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.db import models
from django.utils.translation import gettext_lazy as _
from phonenumber_field.modelfields import PhoneNumberField

from core.utils.constants import CONSTANTS
from .managers import UserManager
from src.core.models import TimestampedModel


class User(AbstractBaseUser, PermissionsMixin, TimestampedModel):
    telegram_id = models.BigIntegerField(unique=True, primary_key=True)
    username = models.CharField(max_length=500)
    first_name = models.CharField(max_length=255)
    last_name = models.CharField(max_length=255, null=True, blank=True)
    phone = PhoneNumberField(null=True, blank=True)
    is_staff = models.BooleanField(
        _("staff status"),
        default=False,
        help_text=_("Designates whether the user can log into this admin site."),
    )
    is_active = models.BooleanField(
        _("active"),
        default=True,
        help_text=_(
            "Designates whether this user should be treated as active. "
            "Unselect this instead of deleting accounts."
        ),
    )
    is_subscribed = models.BooleanField(default=False)
    subscription_start_date = models.DateTimeField(null=True, blank=True)
    subscription_end_date = models.DateTimeField(null=True, blank=True)
    language = models.CharField(max_length=10, choices=CONSTANTS.LANGUAGES.CHOICES, default=CONSTANTS.LANGUAGES.UZ)

    USERNAME_FIELD = 'telegram_id'
    objects = UserManager()

    def __str__(self):
        return f"{self.first_name} - {self.telegram_id}"