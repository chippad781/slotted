from django.conf import settings
from django.db import models
from django.utils.text import slugify


class EventType(models.Model):
    """
    A type of meeting a host offers — e.g. '30 min intro chat'.
    The booking URL ends up like /amogh/intro-chat
    """
    host = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='event_types',
    )
    title = models.CharField(max_length=200)
    slug = models.SlugField(max_length=120)
    description = models.TextField(blank=True)
    duration_minutes = models.PositiveIntegerField(default=30)
    # buffers so we don't get back-to-back meetings with no breathing room
    buffer_before_minutes = models.PositiveIntegerField(default=0)
    buffer_after_minutes = models.PositiveIntegerField(default=0)
    # how far in advance the slot picker shows availability
    advance_days = models.PositiveIntegerField(default=14)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('host', 'slug')
        ordering = ('-created_at',)

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title)[:120]
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.title} ({self.duration_minutes}m) - {self.host.username}"


class AvailabilityRule(models.Model):
    """
    A weekly recurring availability window — e.g.
    Mondays 9:00 to 17:00. Stored in the host's timezone.
    """
    MONDAY = 0
    TUESDAY = 1
    WEDNESDAY = 2
    THURSDAY = 3
    FRIDAY = 4
    SATURDAY = 5
    SUNDAY = 6
    DAY_CHOICES = [
        (MONDAY, 'Monday'),
        (TUESDAY, 'Tuesday'),
        (WEDNESDAY, 'Wednesday'),
        (THURSDAY, 'Thursday'),
        (FRIDAY, 'Friday'),
        (SATURDAY, 'Saturday'),
        (SUNDAY, 'Sunday'),
    ]

    host = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='availability_rules',
    )
    day_of_week = models.IntegerField(choices=DAY_CHOICES)
    start_time = models.TimeField()
    end_time = models.TimeField()

    class Meta:
        ordering = ('day_of_week', 'start_time')

    def __str__(self):
        return f"{self.get_day_of_week_display()} {self.start_time}-{self.end_time}"


class Block(models.Model):
    """
    One-off unavailable time — vacation, conflicts. Stored as UTC.
    Takes priority over availability rules.
    """
    host = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='blocks',
    )
    start = models.DateTimeField()
    end = models.DateTimeField()
    reason = models.CharField(max_length=200, blank=True)

    class Meta:
        ordering = ('start',)
        indexes = [
            models.Index(fields=['host', 'start']),
        ]

    def __str__(self):
        return f"Block {self.start} -> {self.end} ({self.reason or 'no reason'})"


class Booking(models.Model):
    """
    A confirmed appointment between a host and an invitee.
    Times are always stored in UTC.

    The (host, start) unique constraint when status=confirmed is the
    safety net against the double-booking race. The real protection is
    SELECT FOR UPDATE in the booking view, but the DB has our back.
    """
    STATUS_CONFIRMED = 'confirmed'
    STATUS_CANCELLED = 'cancelled'
    STATUS_CHOICES = [
        (STATUS_CONFIRMED, 'Confirmed'),
        (STATUS_CANCELLED, 'Cancelled'),
    ]

    host = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='bookings_as_host',
    )
    event_type = models.ForeignKey(
        EventType,
        on_delete=models.PROTECT,
        related_name='bookings',
    )
    invitee_name = models.CharField(max_length=200)
    invitee_email = models.EmailField()
    invitee_notes = models.TextField(blank=True)
    start = models.DateTimeField()
    end = models.DateTimeField()
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_CONFIRMED,
    )
    cancelled_reason = models.CharField(max_length=200, blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    # idempotency key so a double-clicked submit doesn't create two bookings
    idempotency_key = models.CharField(
        max_length=64, blank=True, null=True, db_index=True,
    )

    class Meta:
        ordering = ('-start',)
        constraints = [
            models.UniqueConstraint(
                fields=['host', 'start'],
                condition=models.Q(status='confirmed'),
                name='unique_host_start_when_confirmed',
            ),
            models.UniqueConstraint(
                fields=['host', 'idempotency_key'],
                condition=models.Q(idempotency_key__isnull=False),
                name='unique_host_idempotency_key',
            ),
        ]
        indexes = [
            models.Index(fields=['host', 'start']),
            models.Index(fields=['invitee_email']),
        ]

    def __str__(self):
        return f"{self.invitee_name} -> {self.host.username} at {self.start}"
