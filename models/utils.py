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


def get_initials(name):
    """Return uppercase initials (first + last) from a display name."""
    if not name:
        return '?'
    parts = name.strip().split()
    if len(parts) >= 2:
        return (parts[0][0] + parts[-1][0]).upper()
    return parts[0][0].upper()
