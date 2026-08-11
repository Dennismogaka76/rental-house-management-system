from django.core.management.base import BaseCommand
from tenancy import services


class Command(BaseCommand):
    help = "Apply late-payment penalty to any active tenancy with balance > 0."

    def handle(self, *args, **options):
        count = services.apply_late_penalties()
        self.stdout.write(self.style.SUCCESS(f"Penalised {count} tenancies."))
