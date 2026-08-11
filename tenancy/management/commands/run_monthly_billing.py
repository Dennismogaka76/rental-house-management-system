from django.core.management.base import BaseCommand
from tenancy import services


class Command(BaseCommand):
    help = "Post monthly rent to every active tenancy."

    def handle(self, *args, **options):
        count = services.run_monthly_billing()
        self.stdout.write(self.style.SUCCESS(f"Billed {count} tenancies."))
