"""Simple in-memory rate limiter for login protection."""
import time
import threading
from collections import defaultdict


class RateLimiter:
    """Track login attempts per IP and per username to prevent brute force."""

    def __init__(self):
        self._lock = threading.Lock()
        # {(ip, username): [(timestamp, success), ...]}
        self._attempts = defaultdict(list)
        # {username: lock_until_timestamp}
        self._locked_accounts = {}

        # Config
        self.max_attempts_per_ip = 10       # per minute per IP
        self.max_attempts_per_account = 5   # per minute per account
        self.window_seconds = 60            # 1 minute sliding window
        self.lockout_seconds = 900          # 15 minutes account lockout after max attempts

    def _cleanup(self):
        """Remove expired entries."""
        now = time.time()
        cutoff = now - self.window_seconds
        with self._lock:
            for key in list(self._attempts.keys()):
                self._attempts[key] = [a for a in self._attempts[key] if a[0] > cutoff]
                if not self._attempts[key]:
                    del self._attempts[key]
            # Cleanup expired lockouts
            for username in list(self._locked_accounts.keys()):
                if self._locked_accounts[username] < now:
                    del self._locked_accounts[username]

    def is_account_locked(self, username: str) -> bool:
        """Check if an account is temporarily locked."""
        self._cleanup()
        with self._lock:
            lock_until = self._locked_accounts.get(username)
            if lock_until and lock_until > time.time():
                return True
        return False

    def check_rate_limit(self, ip: str, username: str) -> tuple[bool, str]:
        """
        Check if the request exceeds rate limits.
        Returns (allowed, reason) where reason is empty string if allowed.
        """
        self._cleanup()
        now = time.time()

        with self._lock:
            # Check account lockout
            if username in self._locked_accounts:
                if self._locked_accounts[username] > now:
                    remaining = int(self._locked_accounts[username] - now)
                    return False, f'Account locked due to too many failed attempts. Try again in {remaining} seconds.'
                else:
                    del self._locked_accounts[username]

            # Check per-account rate limit
            account_key = f'account:{username}'
            account_attempts = [a for a in self._attempts[account_key] if a[0] > now - self.window_seconds]
            if len(account_attempts) >= self.max_attempts_per_account:
                self._locked_accounts[username] = now + self.lockout_seconds
                return False, f'Too many login attempts. Account locked for {self.lockout_seconds // 60} minutes.'

            # Check per-IP rate limit
            ip_key = f'ip:{ip}'
            ip_attempts = [a for a in self._attempts[ip_key] if a[0] > now - self.window_seconds]
            if len(ip_attempts) >= self.max_attempts_per_ip:
                return False, f'Too many requests from this IP. Please try again later.'

        return True, ''

    def record_attempt(self, ip: str, username: str, success: bool):
        """Record a login attempt."""
        now = time.time()
        with self._lock:
            self._attempts[f'ip:{ip}'].append((now, success))
            self._attempts[f'account:{username}'].append((now, success))


# Global instance
login_rate_limiter = RateLimiter()