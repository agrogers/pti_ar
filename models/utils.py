"""Shared formatting helpers for pti_ar display names."""


def fmt_date(d):
    """Format a date as M/D with no leading zeros (cross-platform)."""
    return d.strftime('%m/%d').lstrip('0').replace('/0', '/')


def fmt_time(dt):
    """Format a datetime/time as '3:45p' or '4a' (no leading zero, a/p suffix)."""
    h = dt.hour
    m = dt.minute
    suffix = 'a' if h < 12 else 'p'
    h12 = h % 12 or 12
    if m:
        return f"{h12}:{m:02d}{suffix}"
    return f"{h12}{suffix}"
