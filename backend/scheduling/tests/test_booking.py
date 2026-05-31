"""Tests for the booking flow."""
from datetime import date, datetime, timedelta, time, timezone

import pytest
from django.db import IntegrityError
from django.urls import reverse
from django.utils import timezone as djtz
from rest_framework.test import APIClient

from scheduling.models import Booking


def _next_monday():
    today = djtz.now().date()
    days_ahead = (7 - today.weekday()) % 7 + 7
    return today + timedelta(days=days_ahead)


@pytest.fixture
def api():
    return APIClient()


@pytest.mark.django_db
def test_book_a_slot(api, event_type):
    monday = _next_monday()
    start = datetime.combine(monday, time(10, 0), tzinfo=timezone.utc)
    payload = {
        'event_type_id': event_type.id,
        'start': start.isoformat(),
        'invitee_name': 'Alice',
        'invitee_email': 'alice@example.com',
        'invitee_notes': 'looking forward to it',
    }
    resp = api.post('/api/public/bookings/', payload, format='json')
    assert resp.status_code == 201
    assert Booking.objects.count() == 1

    b = Booking.objects.first()
    assert b.invitee_name == 'Alice'
    assert b.end == start + timedelta(minutes=30)


@pytest.mark.django_db
def test_cant_book_taken_slot(api, event_type):
    monday = _next_monday()
    start = datetime.combine(monday, time(10, 0), tzinfo=timezone.utc)

    p = {
        'event_type_id': event_type.id,
        'start': start.isoformat(),
        'invitee_name': 'Alice',
        'invitee_email': 'alice@example.com',
    }
    r1 = api.post('/api/public/bookings/', p, format='json')
    assert r1.status_code == 201

    p['invitee_name'] = 'Bob'
    p['invitee_email'] = 'bob@example.com'
    r2 = api.post('/api/public/bookings/', p, format='json')
    assert r2.status_code == 409
    assert Booking.objects.count() == 1


@pytest.mark.django_db
def test_cant_book_outside_availability(api, event_type):
    """Booking at 11pm should fail — host is only available 9-5."""
    monday = _next_monday()
    start = datetime.combine(monday, time(23, 0), tzinfo=timezone.utc)
    payload = {
        'event_type_id': event_type.id,
        'start': start.isoformat(),
        'invitee_name': 'Alice',
        'invitee_email': 'alice@example.com',
    }
    resp = api.post('/api/public/bookings/', payload, format='json')
    assert resp.status_code == 409


@pytest.mark.django_db
def test_cant_book_too_soon(api, event_type):
    """Booking less than 1h from now should be rejected."""
    soon = djtz.now() + timedelta(minutes=15)
    # round to even 15min so it fits the slot grid
    soon = soon.replace(minute=(soon.minute // 15) * 15, second=0, microsecond=0)
    payload = {
        'event_type_id': event_type.id,
        'start': soon.isoformat(),
        'invitee_name': 'Alice',
        'invitee_email': 'alice@example.com',
    }
    resp = api.post('/api/public/bookings/', payload, format='json')
    assert resp.status_code == 409


@pytest.mark.django_db
def test_db_unique_constraint_blocks_duplicate(event_type):
    """Even if our application logic missed it, the DB unique constraint
    is the last line of defence."""
    monday = _next_monday()
    start = datetime.combine(monday, time(10, 0), tzinfo=timezone.utc)
    Booking.objects.create(
        host=event_type.host,
        event_type=event_type,
        invitee_name='A', invitee_email='a@x.com',
        start=start, end=start + timedelta(minutes=30),
    )
    with pytest.raises(IntegrityError):
        Booking.objects.create(
            host=event_type.host,
            event_type=event_type,
            invitee_name='B', invitee_email='b@x.com',
            start=start, end=start + timedelta(minutes=30),
        )


@pytest.mark.django_db
def test_idempotency_key_returns_same_booking(api, event_type):
    """Posting twice with the same key should not create two bookings."""
    monday = _next_monday()
    start = datetime.combine(monday, time(10, 0), tzinfo=timezone.utc)
    payload = {
        'event_type_id': event_type.id,
        'start': start.isoformat(),
        'invitee_name': 'Alice',
        'invitee_email': 'alice@example.com',
        'idempotency_key': 'abc-123',
    }
    r1 = api.post('/api/public/bookings/', payload, format='json')
    r2 = api.post('/api/public/bookings/', payload, format='json')
    assert r1.status_code == 201
    assert r2.status_code == 200  # returned existing
    assert Booking.objects.count() == 1
    assert r1.data['id'] == r2.data['id']


@pytest.mark.django_db
def test_public_profile_endpoint(api, event_type):
    resp = api.get(f'/api/public/{event_type.host.username}/')
    assert resp.status_code == 200
    assert resp.data['host']['username'] == event_type.host.username
    assert len(resp.data['event_types']) == 1


@pytest.mark.django_db
def test_public_slots_endpoint(api, event_type):
    today = djtz.now().date()
    resp = api.get(
        f'/api/public/{event_type.host.username}/{event_type.slug}/slots/'
    )
    assert resp.status_code == 200
    assert 'slots' in resp.data
    assert len(resp.data['slots']) > 0
