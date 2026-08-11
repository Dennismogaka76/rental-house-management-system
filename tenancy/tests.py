from decimal import Decimal
from datetime import date

from django.test import TestCase
from django.utils import timezone

from accounts.models import User
from apartments.models import Apartment, Room
from tenancy import services
from tenancy.models import RoomRequest, Tenancy


class ProrationTests(TestCase):
    def test_full_month_on_first(self):
        self.assertEqual(services.prorated_first_balance(Decimal("9000"), date(2025, 6, 1)), Decimal("9000.00"))

    def test_prorated_20_june(self):
        # 30 days in June; days remaining including 20th = 11; daily = 300; total = 3300
        self.assertEqual(services.prorated_first_balance(Decimal("9000"), date(2025, 6, 20)), Decimal("3300.00"))


class ApprovalFlowTests(TestCase):
    def setUp(self):
        self.tenant = User.objects.create_user(
            phone_number="254700000001", password="pass12345",
            full_name="John Doe", id_number="ID001",
        )
        self.admin = User.objects.create_user(
            phone_number="254700000002", password="pass12345",
            full_name="Admin", id_number="ID002", role=User.Role.ADMIN, is_staff=True,
        )
        self.apt = Apartment.objects.create(name="Sunrise", location="Nairobi", total_rooms=2)
        self.room1 = Room.objects.create(apartment=self.apt, room_number="A1", monthly_rent=Decimal("9000"))
        self.room2 = Room.objects.create(apartment=self.apt, room_number="A2", monthly_rent=Decimal("12000"))

    def test_approve_creates_tenancy_and_occupies_room(self):
        req = RoomRequest.objects.create(
            tenant=self.tenant, apartment=self.apt, room=self.room1,
        )
        t = services.approve_room_request(req, self.admin)
        self.room1.refresh_from_db()
        self.assertEqual(self.room1.tenant, self.tenant)
        self.assertTrue(t.active)
        self.assertEqual(t.monthly_rent, Decimal("9000.00"))

    def test_move_between_rooms_frees_old(self):
        r1 = RoomRequest.objects.create(tenant=self.tenant, apartment=self.apt, room=self.room1)
        services.approve_room_request(r1, self.admin)
        r2 = RoomRequest.objects.create(tenant=self.tenant, apartment=self.apt, room=self.room2)
        services.approve_room_request(r2, self.admin)
        self.room1.refresh_from_db(); self.room2.refresh_from_db()
        self.assertIsNone(self.room1.tenant)
        self.assertEqual(self.room2.tenant, self.tenant)
        self.assertEqual(Tenancy.objects.filter(tenant=self.tenant, active=True).count(), 1)


class BillingTests(TestCase):
    def test_monthly_billing_and_penalty(self):
        tenant = User.objects.create_user(
            phone_number="254700000010", password="p", full_name="T", id_number="X1",
        )
        apt = Apartment.objects.create(name="X", location="L")
        room = Room.objects.create(apartment=apt, room_number="1", monthly_rent=Decimal("5000"))
        tenancy = Tenancy.objects.create(tenant=tenant, room=room, monthly_rent=Decimal("5000"),
                                         balance=Decimal("0"))
        services.run_monthly_billing(date(2025, 7, 1))
        tenancy.refresh_from_db()
        self.assertEqual(tenancy.balance, Decimal("5000.00"))
        services.apply_late_penalties(date(2025, 7, 11), penalty_pct=Decimal("0.10"))
        tenancy.refresh_from_db()
        self.assertEqual(tenancy.penalty, Decimal("500.00"))
        # Penalty applied at most once per month:
        services.apply_late_penalties(date(2025, 7, 11), penalty_pct=Decimal("0.10"))
        tenancy.refresh_from_db()
        self.assertEqual(tenancy.penalty, Decimal("500.00"))
