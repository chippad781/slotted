import os
from datetime import time

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from scheduling.models import AvailabilityRule, EventType


class Command(BaseCommand):
    help = "Create a demo host with availability for the public demo link."

    def handle(self, *args, **options):
        User = get_user_model()

        user, created = User.objects.get_or_create(
            username="demo",
            defaults={
                "email": "demo@slotted.app",
                "timezone": "Asia/Kolkata",
            },
        )
        user.set_password(os.environ.get("DEMO_PASSWORD", "changeme"))
        user.save()

        event_type, _ = EventType.objects.get_or_create(
            host=user,
            slug="intro-chat",
            defaults={
                "title": "30 min intro chat",
                "description": "A short demo meeting. Book any available slot.",
                "duration_minutes": 30,
                "buffer_after_minutes": 10,
                "advance_days": 14,
                "is_active": True,
            },
        )

        for day in range(AvailabilityRule.MONDAY, AvailabilityRule.SUNDAY + 1):
            AvailabilityRule.objects.get_or_create(
                host=user,
                day_of_week=day,
                start_time=time(10, 0),
                end_time=time(18, 0),
            )

        self.stdout.write(self.style.SUCCESS(
            f"Demo host ready: /demo/{event_type.slug}"
        ))