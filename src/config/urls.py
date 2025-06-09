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
from core.queue.scheduler import scheduler, check_expired_subscriptions, check_ending_subscriptions


urlpatterns = [
    path('admin/', admin.site.urls),
    path('bot/', include('bot.urls')),
    path('payments/', include('order.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)


scheduler.add_job(check_expired_subscriptions, trigger='cron', hour=3, minute=0)
scheduler.add_job(check_ending_subscriptions, trigger='cron', hour=4, minute=0)
