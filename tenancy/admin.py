from django.contrib import admin
from .models import Tenancy, RoomRequest


@admin.register(Tenancy)
class TenancyAdmin(admin.ModelAdmin):
    list_display = ("tenant", "room", "monthly_rent", "balance", "penalty", "active", "next_due_date")
    list_filter = ("active", "room__apartment")
    search_fields = ("tenant__full_name", "tenant__phone_number", "room__room_number")
    autocomplete_fields = ("tenant", "room")


@admin.register(RoomRequest)
class RoomRequestAdmin(admin.ModelAdmin):
    list_display = ("tenant", "apartment", "room", "status", "created_at", "reviewed_at")
    list_filter = ("status", "apartment")
    search_fields = ("tenant__full_name", "tenant__phone_number", "room__room_number")
    autocomplete_fields = ("tenant", "room", "reviewed_by")
