"""Celery tasks -- thin wrappers around services.py."""
from celery import shared_task
from . import services


@shared_task
def run_monthly_billing():
    return services.run_monthly_billing()


@shared_task
def apply_late_penalties():
    return services.apply_late_penalties()
