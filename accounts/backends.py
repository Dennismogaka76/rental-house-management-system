"""Custom auth backend that authenticates by phone_number."""
from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend


class PhoneBackend(ModelBackend):
    def authenticate(self, request, username=None, password=None, **kwargs):
        UserModel = get_user_model()
        phone = username or kwargs.get("phone_number")
        if not phone or not password:
            return None
        try:
            user = UserModel.objects.get(phone_number=phone.strip())
        except UserModel.DoesNotExist:
            return None
        if user.check_password(password) and self.user_can_authenticate(user):
            return user
        return None
