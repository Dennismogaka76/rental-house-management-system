import os
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model

class Command(BaseCommand):
    def handle(self, *args, **kwargs):
        User = get_user_model()
        phone = os.environ.get('DJANGO_SUPERUSER_PHONE_NUMBER')
        try:
            user = User.objects.get(phone_number=phone)
            user.is_staff = True
            user.is_superuser = True
            user.is_active = True
            user.save()
            self.stdout.write(self.style.SUCCESS(f'Promoted {phone} to superuser.'))
        except User.DoesNotExist:
            self.stdout.write(self.style.ERROR(f'No user found with phone {phone}'))