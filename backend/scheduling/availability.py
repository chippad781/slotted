"""
Slot computation. Given an event type and a date range, compute the
available start times.

Algorithm (kept deliberately straightforward):

1. For each date in the range, find the host's availability rules
   for that weekday.
2. For each rule, generate candidate slots stepping by SLOT_STEP_MINUTES.
3. Throw out slots that:
   - extend past the rule's end_time
   - overlap any Block
   - overlap any existing confirmed Booking (including buffers)
   - are in the past (or within MIN_NOTICE_MINUTES of now)
4. Return the list of valid start datetimes (UTC).

Times are computed in the host's local timezone (so DST works) and
returned as UTC datetimes.
"""
from datetime import datetime, timedelta, time
from zoneinfo import ZoneInfo

from django.core.cache import cache
from django.utils import timezone as djtz

from .models import AvailabilityRule, Block, Booking


SLOT_STEP_MINUTES = 15      # slot grid resolution
MIN_NOTICE_MINUTES = 60     # can't book less than 1h out
CACHE_TTL_SECONDS = 60      # short-lived cache; we invalidate on booking


def _cache_key(host_id, event_type_id, start_date, end_date):
    return f"avail:{host_id}:{event_type_id}:{start_date.isoformat()}:{end_date.isoformat()}"


def invalidate_availability_cache(host_id):
    """
    Called from the booking view when a slot is taken. We use a
    delete_pattern because we don't know which exact date ranges
    were cached.
    """
    try:
        cache.delete_pattern(f"avail:{host_id}:*")
    except AttributeError:
        # cache backend may not support delete_pattern in tests
        cache.clear()


def get_available_slots(event_type, start_date, end_date, invitee_tz=None):
    """
    Returns a list of UTC datetimes representing available slot start times.

    start_date and end_date are date objects.
    invitee_tz is for display only — we don't use it here.
    """
    cache_key = _cache_key(event_type.host_id, event_type.id, start_date, end_date)
    cached = cache.get(cache_key)
    if cached is not None:
        # cached as ISO strings to be JSON safe
        return [datetime.fromisoformat(s) for s in cached]

    host_tz = ZoneInfo(event_type.host.timezone or 'UTC')
    duration = timedelta(minutes=event_type.duration_minutes)
    buf_before = timedelta(minutes=event_type.buffer_before_minutes)
    buf_after = timedelta(minutes=event_type.buffer_after_minutes)

    # Pull all rules / blocks / bookings up front (one query each).
    rules_by_day = {}
    for r in AvailabilityRule.objects.filter(host=event_type.host):
        rules_by_day.setdefault(r.day_of_week, []).append(r)

    # widen the booking/block window slightly to catch ones that overlap
    # the start/end of the date range
    range_start_utc = datetime.combine(start_date, time.min, tzinfo=host_tz).astimezone(ZoneInfo('UTC'))
    range_end_utc = datetime.combine(end_date, time.max, tzinfo=host_tz).astimezone(ZoneInfo('UTC'))

    blocks = list(Block.objects.filter(
        host=event_type.host,
        end__gte=range_start_utc,
        start__lte=range_end_utc,
    ))
    bookings = list(Booking.objects.filter(
        host=event_type.host,
        status=Booking.STATUS_CONFIRMED,
        end__gte=range_start_utc,
        start__lte=range_end_utc,
    ))

    now_utc = djtz.now()
    earliest_bookable = now_utc + timedelta(minutes=MIN_NOTICE_MINUTES)

    slots = []
    current_date = start_date
    while current_date <= end_date:
        weekday = current_date.weekday()
        rules = rules_by_day.get(weekday, [])
        for rule in rules:
            # build the rule window in the host's local tz, then step
            window_start_local = datetime.combine(current_date, rule.start_time, tzinfo=host_tz)
            window_end_local = datetime.combine(current_date, rule.end_time, tzinfo=host_tz)

            cursor = window_start_local
            while cursor + duration <= window_end_local:
                slot_start_utc = cursor.astimezone(ZoneInfo('UTC'))
                slot_end_utc = slot_start_utc + duration

                if slot_start_utc < earliest_bookable:
                    cursor += timedelta(minutes=SLOT_STEP_MINUTES)
                    continue

                # buffer window — we need this clear of other bookings
                buffered_start = slot_start_utc - buf_before
                buffered_end = slot_end_utc + buf_after

                if _overlaps_any(buffered_start, buffered_end, blocks, bookings, buf_before, buf_after):
                    cursor += timedelta(minutes=SLOT_STEP_MINUTES)
                    continue

                slots.append(slot_start_utc)
                cursor += timedelta(minutes=SLOT_STEP_MINUTES)

        current_date += timedelta(days=1)

    # sort + de-dupe (could happen if rules overlap)
    slots = sorted(set(slots))

    cache.set(cache_key, [s.isoformat() for s in slots], CACHE_TTL_SECONDS)
    return slots


def _overlaps_any(start, end, blocks, bookings, buf_before, buf_after):
    """Does [start, end) overlap any block or any existing booking (incl. buffers)?"""
    for b in blocks:
        if b.start < end and b.end > start:
            return True
    for bk in bookings:
        bk_start = bk.start - buf_before
        bk_end = bk.end + buf_after
        if bk_start < end and bk_end > start:
            return True
    return False


def is_slot_available(event_type, start_utc):
    """
    Check if a single slot is bookable. Used by the booking view
    as a pre-check before opening the transaction.
    """
    duration = timedelta(minutes=event_type.duration_minutes)
    end_utc = start_utc + duration
    buf_before = timedelta(minutes=event_type.buffer_before_minutes)
    buf_after = timedelta(minutes=event_type.buffer_after_minutes)

    # 1. Is it in the future + past min notice?
    if start_utc < djtz.now() + timedelta(minutes=MIN_NOTICE_MINUTES):
        return False

    # 2. Does the host have an availability rule that covers it?
    host_tz = ZoneInfo(event_type.host.timezone or 'UTC')
    start_local = start_utc.astimezone(host_tz)
    end_local = end_utc.astimezone(host_tz)
    weekday = start_local.weekday()

    covered = False
    for rule in AvailabilityRule.objects.filter(host=event_type.host, day_of_week=weekday):
        rule_start = datetime.combine(start_local.date(), rule.start_time, tzinfo=host_tz)
        rule_end = datetime.combine(start_local.date(), rule.end_time, tzinfo=host_tz)
        if rule_start <= start_local and end_local <= rule_end:
            covered = True
            break
    if not covered:
        return False

    # 3. Blocks
    block_overlap = Block.objects.filter(
        host=event_type.host,
        start__lt=end_utc,
        end__gt=start_utc,
    ).exists()
    if block_overlap:
        return False

    # 4. Existing confirmed bookings (with buffer window)
    buffered_start = start_utc - buf_before
    buffered_end = end_utc + buf_after
    conflict = Booking.objects.filter(
        host=event_type.host,
        status=Booking.STATUS_CONFIRMED,
        start__lt=buffered_end,
        end__gt=buffered_start,
    ).exists()
    if conflict:
        return False

    return True
