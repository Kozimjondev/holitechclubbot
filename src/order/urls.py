from django.urls import path


from .views import ClickWebhook


urlpatterns = [
    path('prepare/update/', ClickWebhook.as_view())
]
