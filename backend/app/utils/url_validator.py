"""URL validation utilities to prevent SSRF attacks."""
import ipaddress
import socket
from urllib.parse import urlparse


# Internal/private IP ranges that should be blocked
_PRIVATE_NETWORKS = [
    ipaddress.ip_network('127.0.0.0/8'),       # Loopback
    ipaddress.ip_network('10.0.0.0/8'),        # Private (Class A)
    ipaddress.ip_network('172.16.0.0/12'),     # Private (Class B)
    ipaddress.ip_network('192.168.0.0/16'),    # Private (Class C)
    ipaddress.ip_network('169.254.0.0/16'),    # Link-local
    ipaddress.ip_network('0.0.0.0/8'),         # Current network
    ipaddress.ip_network('100.64.0.0/10'),     # Carrier-grade NAT
    ipaddress.ip_network('198.18.0.0/15'),     # Benchmarking
    ipaddress.ip_network('224.0.0.0/4'),       # Multicast
    ipaddress.ip_network('240.0.0.0/4'),       # Reserved
    ipaddress.ip_network('::1/128'),            # IPv6 loopback
    ipaddress.ip_network('fc00::/7'),           # IPv6 unique local
    ipaddress.ip_network('fe80::/10'),          # IPv6 link-local
]


def is_private_ip(host: str) -> bool:
    """Check if a hostname resolves to a private/internal IP address."""
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        # Not a raw IP - try DNS resolution
        try:
            ip = ipaddress.ip_address(socket.gethostbyname(host))
        except (socket.gaierror, OSError):
            return False

    for network in _PRIVATE_NETWORKS:
        if ip in network:
            return True
    return False


def validate_url(url: str) -> tuple[bool, str]:
    """
    Validate a URL for SSRF prevention.
    Returns (is_valid, reason).
    """
    if not url:
        return False, 'URL is empty'

    try:
        parsed = urlparse(url)
    except Exception:
        return False, f'Invalid URL format: {url}'

    # Only allow http/https
    if parsed.scheme not in ('http', 'https'):
        return False, f'URL scheme not allowed: {parsed.scheme}'

    hostname = parsed.hostname
    if not hostname:
        return False, f'URL has no valid hostname: {url}'

    # Check if hostname resolves to private/internal IP
    if is_private_ip(hostname):
        return False, f'Access to internal/private IP address is not allowed: {hostname}'

    return True, ''