from django.conf import settings
from django.urls import path

from .views import process_update

urlpatterns = [
    path('webhook/', process_update, name=settings.BOT_WEBHOOK_PATH),
]