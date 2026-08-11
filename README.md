# Apartment Rental Management System

A production-ready Django 5.x application for managing apartments, rooms,
tenants, rent, and M-Pesa payments.

## Features

- **Custom User model** with phone-number authentication (tenant & admin roles).
- **Apartments & Rooms** CRUD (admin only).
- **Room Requests**: tenants request a room; admins approve/reject.
  Only vacant rooms of the chosen apartment are shown. History is preserved
  (requests are never deleted). Pending → Approved → Rejected ordering.
- **Tenancy** (separate from `RoomRequest`): tracks move-in, monthly rent,
  balance, penalty, deposit, next due date, last payment. One active
  tenancy per tenant (enforced by a partial unique index).
- **Prorated rent** on move-in.
- **Monthly billing** (1st) and **late penalty** (11th, once per month).
- **Payment reminders** on the 5th and 10th.
- **M-Pesa STK Push** via Safaricom Daraja, with idempotent callback handling
  (success / failed / cancelled / timeout / duplicate).
- **PDF receipts** (ReportLab) with landlord & tenancy details.
- **SMS notifications** via Africa's Talking.
- **Email notifications** where an email is on file.
- **Tenant dashboard**: summary cards + profile toggle + payment history.
- **Admin dashboard**: statistics + recent activity + apartment-filtered
  tenancy view sorted by largest balance first.
- **Reports** (PDF, XLSX, CSV): rent collection, outstanding, vacant /
  occupied rooms, payments by month, payments by apartment, late payments,
  tenants.
- **Search & filters** for tenants, apartments, rooms, statuses.
- **Bootstrap 5** responsive UI with sidebar and pagination.
- **Celery Beat** schedules + equivalent Django management commands
  (`run_monthly_billing`, `apply_late_penalties`) usable with cron.

## Quick Start

```bash
# 1. Clone / unzip and enter the project
cd apartment_rental

# 2. Create and activate a virtualenv
python -m venv .venv && source .venv/bin/activate    # Windows: .venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure environment
cp .env.example .env
# then edit .env — DB credentials, MPESA_*, AT_*, EMAIL_*

# 5. Create the PostgreSQL database
createdb apartment_rental       # or use pgAdmin/psql

# 6. Run migrations & create the admin user
python manage.py makemigrations accounts apartments tenancy payments notifications
python manage.py migrate
python manage.py createsuperuser
# createsuperuser will ask for phone_number, full_name, id_number, password

# 7. Run the server
python manage.py runserver
```

Open <http://127.0.0.1:8000/>.

- Tenants register at `/accounts/register/` and sign in with phone + password.
- Superuser access to Django Admin: `/admin/`.

## Scheduled Jobs

### Option A — cron
```
0 1 1 * *  cd /path/to/apartment_rental && .venv/bin/python manage.py run_monthly_billing
0 1 11 * * cd /path/to/apartment_rental && .venv/bin/python manage.py apply_late_penalties
```

### Option B — Celery Beat (requires Redis)
```bash
celery -A config worker -l info
celery -A config beat  -l info
```
Reminders on the 5th/10th and the monthly billing/penalty tasks are already
declared in `config/celery.py`.

## M-Pesa

Set the Daraja sandbox credentials in `.env`. The callback endpoint the
sandbox must reach is:

```
POST {MPESA_CALLBACK_URL}   ->   /payments/mpesa/callback/
```

Expose it publicly (ngrok, Cloudflare Tunnel, or your production URL).

## Tests

```bash
python manage.py test
```

Covers user auth, room-request approval, room-swap, proration, monthly
billing and once-per-month penalty.

## Project Layout

```
config/       Django settings, root URLs, Celery app
accounts/     Custom user model, auth backend, dashboards
apartments/   Apartment & Room models, admin CRUD, vacant-rooms JSON API
tenancy/      RoomRequest, Tenancy, business services, tasks, commands
payments/     Payment model, Daraja STK Push, callback, PDF receipts
notifications/  SMS + Email services, notification log, Celery tasks
reports/      CSV / XLSX / PDF exports
templates/    Bootstrap 5 UI
```

## Notes

- SMS provider integration is soft: if `AT_API_KEY` is empty the app logs
  the message and continues; nothing crashes.
- Email uses the console backend by default; switch `EMAIL_BACKEND` in
  `.env` (or drop the setting to use SMTP with the provided credentials).
- All destructive/monetary operations use `transaction.atomic` and
  `select_for_update` to prevent race conditions.
