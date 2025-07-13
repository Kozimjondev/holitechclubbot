from django.urls import path


from .views import ClickWebhook, TributeWebhookAPIView

urlpatterns = [
    path('prepare/update/', ClickWebhook.as_view()),
    path('tribute/webhook/', TributeWebhookAPIView.as_view())
]
