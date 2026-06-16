"""Small date helpers for the billing period (a month, identified by its 1st)."""

import calendar

from django.utils import timezone


def first_of_this_month():
    """First day of the current month (the period a scheduled run bills toward)."""
    return timezone.localdate().replace(day=1)


def end_of_month(period):
    """Last calendar day of the month containing `period`.

    Used as the billing *cutoff* — a run sweeps every approved, unbilled entry
    dated on or before this, regardless of which month it was logged in.
    `calendar.monthrange` gives the day count (leap years included), so we never
    hand-roll the month-length arithmetic.
    """
    return period.replace(day=calendar.monthrange(period.year, period.month)[1])
