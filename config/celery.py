"""Celery app for scheduled billing and notifications."""
import os
from celery import Celery
from celery.schedules import crontab

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

app = Celery("apartment_rental")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()

# Beat schedule -- these are also exposed via `manage.py` cron-style commands.
app.conf.beat_schedule = {
    "monthly-billing": {
        "task": "tenancy.tasks.run_monthly_billing",
        "schedule": crontab(day_of_month="1", hour=1, minute=0),
    },
    "payment-reminder-5th": {
        "task": "notifications.tasks.send_payment_reminders",
        "schedule": crontab(day_of_month="5", hour=8, minute=0),
    },
    "late-reminder-10th": {
        "task": "notifications.tasks.send_late_reminders",
        "schedule": crontab(day_of_month="10", hour=8, minute=0),
    },
    "apply-penalties-11th": {
        "task": "tenancy.tasks.apply_late_penalties",
        "schedule": crontab(day_of_month="11", hour=1, minute=0),
    },
}
