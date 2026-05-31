from django.contrib import admin

from .models import EventType, AvailabilityRule, Block, Booking


@admin.register(EventType)
class EventTypeAdmin(admin.ModelAdmin):
    list_display = ('title', 'host', 'duration_minutes', 'is_active', 'created_at')
    list_filter = ('is_active', 'duration_minutes')
    search_fields = ('title', 'host__username', 'host__email')


@admin.register(AvailabilityRule)
class AvailabilityRuleAdmin(admin.ModelAdmin):
    list_display = ('host', 'day_of_week', 'start_time', 'end_time')
    list_filter = ('day_of_week',)


@admin.register(Block)
class BlockAdmin(admin.ModelAdmin):
    list_display = ('host', 'start', 'end', 'reason')
    list_filter = ('host',)
    search_fields = ('reason', 'host__username')


@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = (
        'invitee_name', 'invitee_email', 'host',
        'event_type', 'start', 'status',
    )
    list_filter = ('status', 'event_type')
    search_fields = ('invitee_name', 'invitee_email', 'host__username')
    readonly_fields = ('created_at', 'cancelled_at')
