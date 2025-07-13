from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.db import models
from django.utils.translation import gettext_lazy as _
from phonenumber_field.modelfields import PhoneNumberField

from core.utils.constants import CONSTANTS
from .managers import UserManager
from core.models import TimestampedModel


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
    subscription_start_date = models.DateField(null=True, blank=True)
    subscription_end_date = models.DateField(null=True, blank=True)
    language = models.CharField(max_length=10, choices=CONSTANTS.LANGUAGES.CHOICES, default=CONSTANTS.LANGUAGES.UZ)
    agreed_to_terms = models.BooleanField(
        default=False,
        help_text="Foydalanuvchi ommaviy oferta shartlariga roziligini bildiradi."
    )
    is_auto_subscribe = models.BooleanField(default=False)
    is_foreigner = models.BooleanField(default=False)

    USERNAME_FIELD = 'telegram_id'
    objects = UserManager()

    def __str__(self):
        return f"{self.first_name} - {self.telegram_id}"


class UserCard(TimestampedModel):
    class ProcessingType(models.TextChoices):
        HUMO = "humo", _("Humo")
        UZCARD = "uzcard", _("UZCARD")
        VISA = "visa", _("Visa")

    class ServiceType(models.TextChoices):
        CLICK = "click", _("Click")

    name = models.CharField(default="", max_length=20, verbose_name=_("name"))
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    marked_pan = models.CharField(max_length=16, null=True, blank=True)
    expire_date = models.CharField(max_length=4)
    service = models.CharField(max_length=25, choices=ServiceType.choices, default=ServiceType.CLICK)
    is_main = models.BooleanField(default=False, verbose_name=_("main"))

    is_confirmed = models.BooleanField(default=False)
    card_token = models.CharField(max_length=255, verbose_name='given by click')
    processing = models.CharField(max_length=255, null=True)

    class Meta:
        unique_together = ('user', 'marked_pan', 'card_token')
