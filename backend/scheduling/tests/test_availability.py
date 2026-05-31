"""Tests for the slot calculator."""
from datetime import date, datetime, timedelta, time, timezone

import pytest
from django.utils import timezone as djtz

from scheduling.models import AvailabilityRule, Block, Booking
from scheduling.availability import (
    get_available_slots, is_slot_available, invalidate_availability_cache,
)


def _next_monday():
    """Pick a Monday far enough in the future to avoid MIN_NOTICE issues."""
    today = djtz.now().date()
    days_ahead = (7 - today.weekday()) % 7 + 7  # next-next Monday
    return today + timedelta(days=days_ahead)


@pytest.mark.django_db
def test_slots_within_window(event_type):
    invalidate_availability_cache(event_type.host_id)
    monday = _next_monday()
    slots = get_available_slots(event_type, monday, monday)
    # 9am to 5pm with 15min steps and 30min slots = (8*4) - 1 = 31 slots
    # last valid start is 16:30 because 17:00 end
    assert len(slots) == 31
    assert slots[0].hour == 9 and slots[0].minute == 0
    assert slots[-1].hour == 16 and slots[-1].minute == 30


@pytest.mark.django_db
def test_blocks_remove_slots(event_type, host):
    invalidate_availability_cache(host.id)
    monday = _next_monday()
    # block 10:00 - 11:00
    Block.objects.create(
        host=host,
        start=datetime.combine(monday, time(10, 0), tzinfo=timezone.utc),
        end=datetime.combine(monday, time(11, 0), tzinfo=timezone.utc),
        reason='conflict',
    )
    invalidate_availability_cache(host.id)
    slots = get_available_slots(event_type, monday, monday)
    # 9:45, 10:00, 10:15, 10:30 should all be gone (slot would overlap block)
    hours = [(s.hour, s.minute) for s in slots]
    assert (9, 45) not in hours  # would extend into block
    assert (10, 0) not in hours
    assert (10, 30) not in hours
    assert (11, 0) in hours      # ok, doesn't overlap


@pytest.mark.django_db
def test_existing_booking_removes_slot(event_type, host):
    invalidate_availability_cache(host.id)
    monday = _next_monday()
    Booking.objects.create(
        host=host,
        event_type=event_type,
        invitee_name='Other',
        invitee_email='other@example.com',
        start=datetime.combine(monday, time(14, 0), tzinfo=timezone.utc),
        end=datetime.combine(monday, time(14, 30), tzinfo=timezone.utc),
    )
    invalidate_availability_cache(host.id)
    slots = get_available_slots(event_type, monday, monday)
    hours = [(s.hour, s.minute) for s in slots]
    assert (14, 0) not in hours


@pytest.mark.django_db
def test_buffer_keeps_neighbours_free(event_type, host):
    # add 15min buffer before+after, then book 14:00-14:30
    # 13:45 and 14:30 should both be unavailable
    event_type.buffer_before_minutes = 15
    event_type.buffer_after_minutes = 15
    event_type.save()

    monday = _next_monday()
    Booking.objects.create(
        host=host,
        event_type=event_type,
        invitee_name='Other',
        invitee_email='other@example.com',
        start=datetime.combine(monday, time(14, 0), tzinfo=timezone.utc),
        end=datetime.combine(monday, time(14, 30), tzinfo=timezone.utc),
    )
    invalidate_availability_cache(host.id)
    slots = get_available_slots(event_type, monday, monday)
    hours = [(s.hour, s.minute) for s in slots]
    assert (13, 45) not in hours
    assert (14, 30) not in hours
    assert (14, 45) not in hours
    # 13:30 slot ends 14:00 which overlaps the buffered window
    # (13:45-14:45), so it should also be gone:
    assert (13, 30) not in hours
    assert (13, 15) in hours  # this one ends 13:45, safe
    assert (15, 0) in hours   # well clear of the booking


@pytest.mark.django_db
def test_no_slots_on_weekend(event_type):
    # rules only cover Mon-Fri
    invalidate_availability_cache(event_type.host_id)
    today = djtz.now().date()
    days = (5 - today.weekday()) % 7 + 7  # find a Saturday
    saturday = today + timedelta(days=days)
    slots = get_available_slots(event_type, saturday, saturday)
    assert len(slots) == 0


@pytest.mark.django_db
def test_is_slot_available_basic(event_type):
    invalidate_availability_cache(event_type.host_id)
    monday = _next_monday()
    valid = datetime.combine(monday, time(10, 0), tzinfo=timezone.utc)
    invalid = datetime.combine(monday, time(20, 0), tzinfo=timezone.utc)
    assert is_slot_available(event_type, valid) is True
    assert is_slot_available(event_type, invalid) is False
