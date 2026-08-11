from django.test import TestCase
from accounts.models import User


class UserModelTests(TestCase):
    def test_create_user_and_auth(self):
        u = User.objects.create_user(phone_number="254700111111", password="secret123",
                                     full_name="Jane", id_number="JN1")
        self.assertTrue(u.check_password("secret123"))
        self.assertTrue(u.is_tenant)
        self.assertFalse(u.is_staff)

    def test_unique_phone_and_id(self):
        User.objects.create_user(phone_number="254700111112", password="x",
                                 full_name="A", id_number="A1")
        with self.assertRaises(Exception):
            User.objects.create_user(phone_number="254700111112", password="x",
                                     full_name="B", id_number="A2")
