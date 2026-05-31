"""
Async tasks. Right now this is all email — sending confirmations,
sending reminders, sending cancellation notices.

Why these are async: we don't want the booking POST to block on an
SMTP round trip. We also use apply_async with eta for the 24h reminder
so we don't need a separate cron.
"""
from celery import shared_task
from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string

from .models import Booking


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_confirmation_email(self, booking_id):
    try:
        booking = Booking.objects.select_related('host', 'event_type').get(pk=booking_id)
    except Booking.DoesNotExist:
        return

    subject = f"Booking confirmed: {booking.event_type.title} with {booking.host.display_name or booking.host.username}"
    body = _build_confirmation_body(booking)
    try:
        send_mail(
            subject,
            body,
            settings.DEFAULT_FROM_EMAIL,
            [booking.invitee_email, booking.host.email],
            fail_silently=False,
        )
    except Exception as exc:
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_reminder_email(self, booking_id):
    try:
        booking = Booking.objects.select_related('host', 'event_type').get(pk=booking_id)
    except Booking.DoesNotExist:
        return

    # don't bother if it was cancelled
    if booking.status != Booking.STATUS_CONFIRMED:
        return

    subject = f"Reminder: {booking.event_type.title} tomorrow"
    body = _build_reminder_body(booking)
    try:
        send_mail(
            subject,
            body,
            settings.DEFAULT_FROM_EMAIL,
            [booking.invitee_email, booking.host.email],
            fail_silently=False,
        )
    except Exception as exc:
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_cancellation_email(self, booking_id):
    try:
        booking = Booking.objects.select_related('host', 'event_type').get(pk=booking_id)
    except Booking.DoesNotExist:
        return

    subject = f"Booking cancelled: {booking.event_type.title}"
    body = (
        f"Hi {booking.invitee_name},\n\n"
        f"Your booking with {booking.host.display_name or booking.host.username} "
        f"for {booking.start.strftime('%A, %d %B at %H:%M UTC')} has been cancelled.\n\n"
        f"Reason: {booking.cancelled_reason or 'no reason given'}\n\n"
        f"You can rebook at {settings.FRONTEND_URL}/{booking.host.username}\n"
    )
    try:
        send_mail(
            subject, body, settings.DEFAULT_FROM_EMAIL,
            [booking.invitee_email, booking.host.email], fail_silently=False,
        )
    except Exception as exc:
        raise self.retry(exc=exc)


def _build_confirmation_body(booking):
    return (
        f"Hi {booking.invitee_name},\n\n"
        f"Your booking is confirmed.\n\n"
        f"What:  {booking.event_type.title}\n"
        f"With:  {booking.host.display_name or booking.host.username}\n"
        f"When:  {booking.start.strftime('%A, %d %B %Y at %H:%M UTC')}\n"
        f"Length: {booking.event_type.duration_minutes} minutes\n\n"
        f"Notes from you: {booking.invitee_notes or '(none)'}\n\n"
        f"To cancel, contact {booking.host.email}.\n"
    )


def _build_reminder_body(booking):
    return (
        f"Hi {booking.invitee_name},\n\n"
        f"Quick reminder of your booking tomorrow.\n\n"
        f"What:  {booking.event_type.title}\n"
        f"With:  {booking.host.display_name or booking.host.username}\n"
        f"When:  {booking.start.strftime('%A, %d %B %Y at %H:%M UTC')}\n\n"
        f"See you then!\n"
    )
