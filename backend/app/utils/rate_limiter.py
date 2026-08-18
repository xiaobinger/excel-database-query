"""Rate limiter for login protection. Account lock state persisted in DB."""
import time
import threading
from collections import defaultdict
from datetime import datetime


class RateLimiter:
    """Track login attempts per IP and per username to prevent brute force."""

    def __init__(self, lockout_seconds=300):
        self._lock = threading.Lock()
        # {(ip or account_key): [(timestamp, success), ...]}
        self._attempts = defaultdict(list)

        # Config
        self.max_attempts_per_ip = 10       # per minute per IP
        self.max_attempts_per_account = 5   # per minute per account
        self.window_seconds = 60            # 1 minute sliding window
        self.lockout_seconds = lockout_seconds

    def _cleanup(self):
        """Remove expired attempt entries."""
        now = time.time()
        cutoff = now - self.window_seconds
        with self._lock:
            for key in list(self._attempts.keys()):
                self._attempts[key] = [a for a in self._attempts[key] if a[0] > cutoff]
                if not self._attempts[key]:
                    del self._attempts[key]

    def is_account_locked(self, username: str) -> bool:
        """Check if an account is locked (from DB)."""
        from app import db
        from app.models.user import User
        user = User.query.filter_by(username=username).first()
        if user and user.lock_until and user.lock_until > datetime.utcnow():
            return True
        return False

    def _lock_account(self, username: str):
        """Persist account lock to DB."""
        from app import db
        from app.models.user import User
        from datetime import timedelta
        user = User.query.filter_by(username=username).first()
        if user:
            user.lock_until = datetime.utcnow() + timedelta(seconds=self.lockout_seconds)
            try:
                db.session.commit()
            except Exception:
                db.session.rollback()

    def _unlock_account(self, username: str):
        """Clear account lock in DB."""
        from app import db
        from app.models.user import User
        user = User.query.filter_by(username=username).first()
        if user and user.lock_until:
            user.lock_until = None
            try:
                db.session.commit()
            except Exception:
                db.session.rollback()

    def check_rate_limit(self, ip: str, username: str) -> tuple[bool, str]:
        """
        Check if the request exceeds rate limits.
        Returns (allowed, reason) where reason is empty string if allowed.
        """
        self._cleanup()
        now = time.time()

        # Check account lockout from DB
        if self.is_account_locked(username):
            from app import db
            from app.models.user import User
            user = User.query.filter_by(username=username).first()
            if user and user.lock_until:
                remaining = max(0, int((user.lock_until - datetime.utcnow()).total_seconds()))
                return False, f'Account locked due to too many failed attempts. Try again in {remaining} seconds.'

        with self._lock:
            # Check per-account rate limit
            account_key = f'account:{username}'
            account_attempts = [a for a in self._attempts[account_key] if a[0] > now - self.window_seconds]
            if len(account_attempts) >= self.max_attempts_per_account:
                self._lock_account(username)
                return False, f'Too many login attempts. Account locked for {self.lockout_seconds // 60} minutes.'

            # Check per-IP rate limit
            ip_key = f'ip:{ip}'
            ip_attempts = [a for a in self._attempts[ip_key] if a[0] > now - self.window_seconds]
            if len(ip_attempts) >= self.max_attempts_per_ip:
                return False, f'Too many requests from this IP. Please try again later.'

        return True, ''

    def record_attempt(self, ip: str, username: str, success: bool):
        """Record a login attempt. On success, clear any existing lock."""
        now = time.time()
        with self._lock:
            self._attempts[f'ip:{ip}'].append((now, success))
            self._attempts[f'account:{username}'].append((now, success))
        if success:
            self._unlock_account(username)


# Global instance (lockout_seconds set via init_app after config loaded)
login_rate_limiter = RateLimiter()


def init_rate_limiter(app):
    """Initialize rate limiter with app config."""
    lockout_seconds = app.config.get('LOGIN_LOCKOUT_SECONDS', 300)
    login_rate_limiter.lockout_seconds = lockout_seconds