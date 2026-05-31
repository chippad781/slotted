from rest_framework import serializers

from .models import EventType, AvailabilityRule, Block, Booking
from accounts.serializers import PublicUserSerializer


class EventTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = EventType
        fields = (
            'id', 'title', 'slug', 'description',
            'duration_minutes', 'buffer_before_minutes', 'buffer_after_minutes',
            'advance_days', 'is_active', 'created_at',
        )
        read_only_fields = ('id', 'created_at')

    def validate_duration_minutes(self, value):
        if value < 5 or value > 480:
            raise serializers.ValidationError("Duration must be between 5 and 480 minutes.")
        return value


class PublicEventTypeSerializer(serializers.ModelSerializer):
    """What we expose to invitees on the public page."""
    host = PublicUserSerializer(read_only=True)

    class Meta:
        model = EventType
        fields = (
            'id', 'title', 'slug', 'description',
            'duration_minutes', 'advance_days', 'host',
        )


class AvailabilityRuleSerializer(serializers.ModelSerializer):
    class Meta:
        model = AvailabilityRule
        fields = ('id', 'day_of_week', 'start_time', 'end_time')

    def validate(self, attrs):
        if attrs['start_time'] >= attrs['end_time']:
            raise serializers.ValidationError("start_time must be before end_time.")
        return attrs


class BlockSerializer(serializers.ModelSerializer):
    class Meta:
        model = Block
        fields = ('id', 'start', 'end', 'reason')

    def validate(self, attrs):
        if attrs['start'] >= attrs['end']:
            raise serializers.ValidationError("start must be before end.")
        return attrs


class BookingSerializer(serializers.ModelSerializer):
    """Serializer for the host viewing their own bookings."""
    event_type_title = serializers.CharField(source='event_type.title', read_only=True)
    duration_minutes = serializers.IntegerField(source='event_type.duration_minutes', read_only=True)

    class Meta:
        model = Booking
        fields = (
            'id', 'event_type', 'event_type_title', 'duration_minutes',
            'invitee_name', 'invitee_email', 'invitee_notes',
            'start', 'end', 'status', 'cancelled_reason',
            'cancelled_at', 'created_at',
        )
        read_only_fields = (
            'id', 'event_type_title', 'duration_minutes',
            'end', 'cancelled_at', 'created_at',
        )


class CreateBookingSerializer(serializers.Serializer):
    """
    Input for the public booking endpoint.
    We don't use a ModelSerializer here because the input shape
    (just slot start) doesn't match the model's shape (start+end).
    """
    event_type_id = serializers.IntegerField()
    start = serializers.DateTimeField()
    invitee_name = serializers.CharField(max_length=200)
    invitee_email = serializers.EmailField()
    invitee_notes = serializers.CharField(required=False, allow_blank=True, max_length=2000)
    idempotency_key = serializers.CharField(required=False, allow_blank=True, max_length=64)
