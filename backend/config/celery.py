import os

from celery import Celery
from celery.signals import setup_logging

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

app = Celery('yunojuno')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()


@setup_logging.connect
def configure_logging(**kwargs):
    """Point the Celery worker at Django's LOGGING config instead of Celery's own,
    so task logs (e.g. the billing run) are formatted and levelled identically."""
    from logging.config import dictConfig

    from django.conf import settings

    dictConfig(settings.LOGGING)
