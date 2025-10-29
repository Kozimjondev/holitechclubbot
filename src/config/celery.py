import os

from celery import Celery
from celery.schedules import crontab


os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

app = Celery('config')

app.config_from_object('django.conf:settings', namespace='CELERY')  # Remove f-string

app.autodiscover_tasks()

app.conf.beat_schedule = {
    'send-expiration-notifications': {
        'task': 'core.tasks.send_membership_expire_notification',
        'schedule': crontab(hour=6, minute=0),
    },
    'first-payment-attempt': {
        'task': 'core.tasks.process_expired_subscriptions',
        'schedule': crontab(hour=22, minute=30),
    },
    'second-payment-attempt-and-kick': {
        'task': 'core.tasks.kick_unpaid_users',
        'schedule': crontab(hour=23, minute=30),
    },
}