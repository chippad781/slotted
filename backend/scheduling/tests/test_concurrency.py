"""
Test the double-booking race head-on.

Two threads try to grab the same slot at the same time. Exactly one
should win, the other should get a 409. This is the test we point at
when interviewers ask "how did you prevent double-booking?"
"""
import threading
from datetime import datetime, timedelta, time, timezone

import pytest
from django.db import connection, connections
from django.test.utils import override_settings
from django.utils import timezone as djtz
from rest_framework.test import APIClient

from scheduling.models import Booking


def _next_monday():
    today = djtz.now().date()
    days_ahead = (7 - today.weekday()) % 7 + 7
    return today + timedelta(days=days_ahead)


@pytest.mark.django_db(transaction=True)
def test_two_simultaneous_bookings_only_one_wins(event_type):
    """
    Fire two POSTs from two threads. Each thread gets its own DB
    connection so they don't share the test transaction. Exactly one
    should succeed.
    """
    monday = _next_monday()
    start = datetime.combine(monday, time(11, 0), tzinfo=timezone.utc)

    results = []

    def book(name):
        # Each thread needs its own connection
        connections.close_all()
        client = APIClient()
        resp = client.post('/api/public/bookings/', {
            'event_type_id': event_type.id,
            'start': start.isoformat(),
            'invitee_name': name,
            'invitee_email': f'{name.lower()}@example.com',
        }, format='json')
        results.append(resp.status_code)

    t1 = threading.Thread(target=book, args=('Alice',))
    t2 = threading.Thread(target=book, args=('Bob',))
    t1.start(); t2.start()
    t1.join(); t2.join()

    # Exactly one win, exactly one loss
    assert sorted(results) == [201, 409], f"unexpected: {results}"
    assert Booking.objects.filter(status='confirmed').count() == 1
