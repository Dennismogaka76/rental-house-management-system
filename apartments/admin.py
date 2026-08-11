from django.contrib import admin
from .models import Apartment, Room


class RoomInline(admin.TabularInline):
    model = Room
    extra = 0
    fields = ("room_number", "floor", "room_type", "monthly_rent", "tenant")
    readonly_fields = ("tenant",)


@admin.register(Apartment)
class ApartmentAdmin(admin.ModelAdmin):
    list_display = ("name", "location", "total_rooms", "occupied_count", "vacant_count", "created_at")
    search_fields = ("name", "location")
    inlines = (RoomInline,)


@admin.register(Room)
class RoomAdmin(admin.ModelAdmin):
    list_display = ("apartment", "room_number", "floor", "room_type", "monthly_rent", "tenant", "created_at")
    list_filter = ("apartment", "room_type")
    search_fields = ("room_number", "apartment__name")
    autocomplete_fields = ("tenant",)
