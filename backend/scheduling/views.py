from datetime import datetime, timedelta, date

from django.contrib.auth import get_user_model
from django.db import transaction, IntegrityError
from django.shortcuts import get_object_or_404
from rest_framework import viewsets, permissions, status
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.throttling import ScopedRateThrottle, AnonRateThrottle

from .models import EventType, AvailabilityRule, Block, Booking
from .serializers import (
    EventTypeSerializer, PublicEventTypeSerializer,
    AvailabilityRuleSerializer, BlockSerializer,
    BookingSerializer, CreateBookingSerializer,
)
from .availability import (
    get_available_slots, is_slot_available, invalidate_availability_cache,
)
from . import tasks

User = get_user_model()


# ---------- host (authenticated) endpoints ----------

class EventTypeViewSet(viewsets.ModelViewSet):
    serializer_class = EventTypeSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return EventType.objects.filter(host=self.request.user)

    def perform_create(self, serializer):
        serializer.save(host=self.request.user)


class AvailabilityRuleViewSet(viewsets.ModelViewSet):
    serializer_class = AvailabilityRuleSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return AvailabilityRule.objects.filter(host=self.request.user)

    def perform_create(self, serializer):
        serializer.save(host=self.request.user)
        # bookings depend on availability; if rules change, blow the cache
        invalidate_availability_cache(self.request.user.id)

    def perform_update(self, serializer):
        serializer.save()
        invalidate_availability_cache(self.request.user.id)

    def perform_destroy(self, instance):
        instance.delete()
        invalidate_availability_cache(self.request.user.id)


class BlockViewSet(viewsets.ModelViewSet):
    serializer_class = BlockSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Block.objects.filter(host=self.request.user)

    def perform_create(self, serializer):
        serializer.save(host=self.request.user)
        invalidate_availability_cache(self.request.user.id)

    def perform_destroy(self, instance):
        instance.delete()
        invalidate_availability_cache(self.request.user.id)


class BookingViewSet(viewsets.ReadOnlyModelViewSet):
    """Host views their bookings here. Creating bookings happens via the public endpoint."""
    serializer_class = BookingSerializer
    permission_classes = [permissions.IsAuthenticated]
    filterset_fields = ['status']

    def get_queryset(self):
        qs = Booking.objects.filter(host=self.request.user).select_related('event_type')
        upcoming = self.request.query_params.get('upcoming')
        if upcoming == 'true':
            from django.utils import timezone
            qs = qs.filter(end__gte=timezone.now())
        return qs


class CancelBookingView(APIView):
    """Host cancels one of their bookings."""
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        booking = get_object_or_404(
            Booking, pk=pk, host=request.user, status=Booking.STATUS_CONFIRMED
        )
        from django.utils import timezone
        booking.status = Booking.STATUS_CANCELLED
        booking.cancelled_at = timezone.now()
        booking.cancelled_reason = request.data.get('reason', '')
        booking.save()
        invalidate_availability_cache(request.user.id)
        # fire-and-forget email
        tasks.send_cancellation_email.delay(booking.id)
        return Response(BookingSerializer(booking).data)


# ---------- public (unauthenticated) endpoints ----------

class PublicProfileView(APIView):
    """GET /api/public/<username>/ — the host's public page."""
    permission_classes = [permissions.AllowAny]
    throttle_classes = [AnonRateThrottle]

    def get(self, request, username):
        user = get_object_or_404(User, username__iexact=username)
        event_types = EventType.objects.filter(host=user, is_active=True)
        return Response({
            'host': {
                'username': user.username,
                'display_name': user.display_name or user.username,
                'bio': user.bio,
                'timezone': user.timezone,
            },
            'event_types': PublicEventTypeSerializer(event_types, many=True).data,
        })


class PublicSlotsView(APIView):
    """
    GET /api/public/<username>/<event_slug>/slots/?from=YYYY-MM-DD&to=YYYY-MM-DD
    Returns available start times as ISO strings (UTC).
    """
    permission_classes = [permissions.AllowAny]
    throttle_classes = [AnonRateThrottle]

    def get(self, request, username, event_slug):
        user = get_object_or_404(User, username__iexact=username)
        event_type = get_object_or_404(
            EventType, host=user, slug=event_slug, is_active=True
        )

        try:
            start_date = self._parse_date(request.query_params.get('from'), default=date.today())
            end_date = self._parse_date(
                request.query_params.get('to'),
                default=start_date + timedelta(days=event_type.advance_days),
            )
        except ValueError:
            return Response(
                {'detail': 'Invalid date. Use YYYY-MM-DD.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Cap the range so nobody asks for the next 10 years
        if (end_date - start_date).days > 60:
            end_date = start_date + timedelta(days=60)

        slots = get_available_slots(event_type, start_date, end_date)
        return Response({
            'event_type': PublicEventTypeSerializer(event_type).data,
            'from': start_date.isoformat(),
            'to': end_date.isoformat(),
            'slots': [s.isoformat() for s in slots],
        })

    def _parse_date(self, value, default):
        if not value:
            return default
        return datetime.strptime(value, '%Y-%m-%d').date()


class CreateBookingView(APIView):
    """
    POST /api/public/bookings/
    The actual concurrency-critical endpoint.
    """
    permission_classes = [permissions.AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'booking_create'

    def post(self, request):
        serializer = CreateBookingSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        event_type = get_object_or_404(
            EventType, pk=data['event_type_id'], is_active=True
        )
        start_utc = data['start']
        end_utc = start_utc + timedelta(minutes=event_type.duration_minutes)

        # Idempotency: if the same key shows up again for this host, return
        # the existing booking instead of creating a duplicate.
        idem = data.get('idempotency_key') or None
        if idem:
            existing = Booking.objects.filter(
                host=event_type.host, idempotency_key=idem
            ).first()
            if existing:
                return Response(
                    BookingSerializer(existing).data, status=status.HTTP_200_OK
                )

        # Cheap pre-check before opening a transaction. The real check
        # happens inside the transaction below.
        if not is_slot_available(event_type, start_utc):
            return Response(
                {'detail': 'That time is no longer available.'},
                status=status.HTTP_409_CONFLICT,
            )

        try:
            with transaction.atomic():
                # Lock the host's row to serialize concurrent booking attempts.
                # Anyone else trying to book this host has to wait here.
                # This is the heart of how we prevent double-booking.
                User.objects.select_for_update().get(pk=event_type.host_id)

                # Re-check inside the lock — the world may have changed
                # while we were waiting.
                if not is_slot_available(event_type, start_utc):
                    return Response(
                        {'detail': 'That time was just taken. Please pick another.'},
                        status=status.HTTP_409_CONFLICT,
                    )

                booking = Booking.objects.create(
                    host=event_type.host,
                    event_type=event_type,
                    invitee_name=data['invitee_name'],
                    invitee_email=data['invitee_email'],
                    invitee_notes=data.get('invitee_notes', ''),
                    start=start_utc,
                    end=end_utc,
                    idempotency_key=idem,
                )
        except IntegrityError:
            # Belt + suspenders: the unique constraint caught a race we missed.
            return Response(
                {'detail': 'That time was just taken. Please pick another.'},
                status=status.HTTP_409_CONFLICT,
            )

        invalidate_availability_cache(event_type.host_id)

        # Async: send confirmation, schedule reminder
        tasks.send_confirmation_email.delay(booking.id)
        tasks.send_reminder_email.apply_async(
            args=[booking.id],
            eta=booking.start - timedelta(hours=24),
        )

        return Response(
            BookingSerializer(booking).data, status=status.HTTP_201_CREATED
        )
