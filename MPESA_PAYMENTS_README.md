# Lipa na M-Pesa Payments — How It Works & How To Change It

Current configuration shipped with the project:

| Setting | Value |
|---|---|
| Paybill (Business Number) | **852648** |
| Account Number | **105713** |
| Environment | `sandbox` (switch to `production` when you go live) |

---

## 1. The two ways a tenant can pay

### A. STK Push (automatic)
1. Tenant opens **Pay Rent**, enters phone number + amount, clicks **Pay via M-Pesa**.
2. The app calls Safaricom's Daraja API (`/mpesa/stkpush/v1/processrequest`) with
   your Paybill as `BusinessShortCode`/`PartyB` and `105713` as `AccountReference`.
3. A payment row is saved with status **Pending**.
4. The tenant enters their M-Pesa PIN on the phone.
5. Safaricom sends a **callback** to `MPESA_CALLBACK_URL`
   (`/payments/mpesa/callback/`) with the result.
6. On success the app marks the payment **Success**, saves the M-Pesa receipt,
   clears the penalty first and then the rent balance, records
   `balance_before` / `balance_after`, and notifies the tenant.
   If the tenant pays more than owed, the balance goes negative — that is the
   overpayment credit shown on the dashboard.

### B. Manual Paybill (works even if the callback can't reach you)
1. Tenant pays on their phone: **M-PESA → Lipa na M-Pesa → Pay Bill →
   Business no. 852648 → Account no. 105713 → amount → PIN**.
2. On the **Pay Rent** page they paste the M-Pesa confirmation code and the
   amount, and submit.
3. The payment is stored as **Pending**.
4. Admin opens **Payments → All Payments**, checks the code against the
   Safaricom statement / SMS, and clicks **Verify**. The balance updates
   immediately, exactly like an STK payment.

---

## 2. Does the app have to be online to use the Paybill?

**Short answer: the Paybill itself works offline; automatic reconciliation does not.**

- **Money always reaches your Paybill.** A tenant can pay 852648 / 105713 from
  their phone whether your app is running or not — that transaction is between
  the tenant and Safaricom.
- **STK Push requires the app to be online** with internet access, because the
  server has to call Daraja to trigger the prompt.
- **Automatic balance updates require a public HTTPS URL.** Safaricom must be
  able to reach your callback endpoint from the internet. On `localhost` it
  cannot, so nothing updates automatically. Options:
  - Deploy the app (any host with a public HTTPS domain), or
  - Use a tunnel while testing: `ngrok http 8000`, then set
    `MPESA_CALLBACK_URL=https://<your-ngrok-id>.ngrok.io/payments/mpesa/callback/`.
- **If you never expose the app publicly**, use the manual Paybill flow above —
  tenants pay offline and the admin verifies the code. Balances stay accurate.

Also note: Safaricom only accepts **HTTPS** callback URLs on production, and the
Paybill must be registered/enabled for Daraja C2B & STK on the
[Daraja portal](https://developer.safaricom.co.ke).

---

## 3. How to change to different payment details

All values come from environment variables (`.env` file at the project root) —
no code editing needed.

```env
# .env
MPESA_ENV=production              # or sandbox for testing
MPESA_PAYBILL=852648              # <-- your Paybill / business number
MPESA_ACCOUNT_NUMBER=105713       # <-- your account number
MPESA_BUSINESS_NAME=Apartment Rentals
MPESA_SHORTCODE=852648            # usually the same as the Paybill
MPESA_PASSKEY=your-daraja-passkey
MPESA_CONSUMER_KEY=your-daraja-consumer-key
MPESA_CONSUMER_SECRET=your-daraja-consumer-secret
MPESA_CALLBACK_URL=https://yourdomain.com/payments/mpesa/callback/
```

Then restart the server. The new Paybill and account number appear automatically
on the Pay Rent page instructions and in the STK Push request.

**Where each value comes from**
- `MPESA_PAYBILL` / `MPESA_SHORTCODE` — your Safaricom business short code.
- `MPESA_PASSKEY` — Daraja portal → your app → Lipa na M-Pesa Online passkey.
- `MPESA_CONSUMER_KEY` / `MPESA_CONSUMER_SECRET` — Daraja portal → My Apps.
- `MPESA_CALLBACK_URL` — your public domain + `/payments/mpesa/callback/`.

**Defaults if you edit code instead:** `config/settings.py`, lines under
`# --- Lipa na M-Pesa (Paybill) ---`.

---

## 4. Files involved

| File | Role |
|---|---|
| `config/settings.py` | Paybill, account number, Daraja credentials |
| `payments/mpesa.py` | STK push, callback handling, balance allocation, manual payment recording/verification |
| `payments/views.py` | Pay page, manual submission, admin verification, callback endpoint |
| `payments/urls.py` | `/payments/pay/`, `/payments/pay/manual/`, `/payments/mpesa/callback/`, `/payments/admin/verify/<pk>/` |
| `templates/payments/pay.html` | STK form + Lipa na M-Pesa instructions |
| `templates/payments/admin_list.html` | Admin "Verify" button for manual payments |
| `payments/receipts.py` | PDF receipt after a successful payment |

---

## 5. Testing without real money

Set `MPESA_ENV=sandbox` and use Daraja sandbox credentials with test shortcode
`174379` and the sandbox test MSISDN. Or simply use the manual flow with a fake
code to confirm the balance arithmetic (penalty first, then rent, negative
balance = overpayment).
