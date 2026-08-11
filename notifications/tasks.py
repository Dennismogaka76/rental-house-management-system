from celery import shared_task
from tenancy.models import Tenancy
from . import services


@shared_task
def send_payment_reminders():
    n = 0
    for t in Tenancy.objects.filter(active=True, balance__gt=0):
        services.notify_payment_reminder(t)
        n += 1
    return n


@shared_task
def send_late_reminders():
    n = 0
    for t in Tenancy.objects.filter(active=True, balance__gt=0):
        services.notify_late_reminder(t)
        n += 1
    return n
