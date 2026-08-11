from django.contrib import admin
from .models import Payment


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ("reference_number", "tenant", "amount", "payment_method", "status", "transaction_date")
    list_filter = ("status", "payment_method", "transaction_date")
    search_fields = ("reference_number", "mpesa_receipt", "tenant__full_name", "tenant__phone_number")
    readonly_fields = ("balance_before", "balance_after", "checkout_request_id", "merchant_request_id")
