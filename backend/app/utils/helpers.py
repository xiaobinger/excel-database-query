from datetime import datetime, timedelta, timezone

BEIJING_TZ = timezone(timedelta(hours=8))


def beijing_now():
    return datetime.now(BEIJING_TZ)


def utc_to_beijing(dt):
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(BEIJING_TZ)


def format_beijing(dt, fmt='%Y-%m-%d %H:%M:%S'):
    if dt is None:
        return None
    bj = utc_to_beijing(dt)
    return bj.strftime(fmt)


def beijing_isoformat(dt):
    if dt is None:
        return None
    bj = utc_to_beijing(dt)
    return bj.strftime('%Y-%m-%dT%H:%M:%S')
