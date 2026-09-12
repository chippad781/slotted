import pytest
from datetime import time
from django.contrib.auth import get_user_model

from scheduling.models import EventType, AvailabilityRule

User = get_user_model()


@pytest.fixture
def host(db):
    return User.objects.create_user(
        email='host@example.com',
        username='host',
        password='strongpass123!',
        display_name='Host User',
        timezone='UTC',
    )


@pytest.fixture
def event_type(host):
    et = EventType.objects.create(
        host=host,
        title='30 min chat',
        slug='30-min-chat',
        duration_minutes=30,
    )
    # available every weekday 9am-5pm UTC
    for day in range(0, 5):  # Mon..Fri
        AvailabilityRule.objects.create(
            host=host,
            day_of_week=day,
            start_time=time(9, 0),
            end_time=time(17, 0),
        )
    return et

@pytest.fixture(autouse=True)
def clear_cache_between_tests():
    """
    DRF throttling and availability caching both use the Django cache.
    Without clearing it, throttle counters leak across tests and the
    suite's result depends on execution order.
    """
    from django.core.cache import cache
    cache.clear()
    yield
    cache.clear()
