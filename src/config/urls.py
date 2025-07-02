"""
URL configuration for config project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include

from config import settings
from django.contrib.staticfiles.urls import static
from core.queue.scheduler import remove_user_from_channels_sync, kick_unpaid_users_handler_sync, scheduler


urlpatterns = [
    path('admin/', admin.site.urls),
    path('v1/bot/', include('bot.urls')),
    path('payments/', include('order.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)


# if settings.RUN_SCHEDULER:
#     scheduler.add_job(
#         remove_user_from_channels_sync,
#         trigger='cron',
#         hour=22,
#         minute=30,
#         id='first_payment_attempt'
#     )
#     scheduler.add_job(
#         kick_unpaid_users_handler_sync,
#         trigger='cron',
#         hour=23,
#         minute=30,
#         id='second_payment_attempt_and_kick'
#     )