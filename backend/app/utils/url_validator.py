"""URL validation utilities with SSRF safeguards for external resource fetching."""
from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlparse

# Private and reserved IP blocks to block for SSRF prevention
BLOCKED_NETWORKS = [
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("169.254.0.0/16"),
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fc00::/7"),
    ipaddress.ip_network("fe80::/10"),
]

ALLOWED_SCHEMES = {"http", "https"}


def is_safe_url(url: str) -> bool:
    """Check whether a URL is syntactically valid and does not point to internal/loopback IPs."""
    if not url or not isinstance(url, str):
        return False

    url = url.strip()
    if len(url) > 2048:
        return False

    try:
        parsed = urlparse(url)
        if parsed.scheme.lower() not in ALLOWED_SCHEMES:
            return False

        hostname = parsed.hostname
        if not hostname:
            return False

        # Check if direct IP address
        try:
            ip = ipaddress.ip_address(hostname)
            for blocked in BLOCKED_NETWORKS:
                if ip in blocked:
                    return False
        except ValueError:
            # Hostname is a domain name - resolve to verify destination IP
            try:
                addr_info = socket.getaddrinfo(hostname, None)
                for addr in addr_info:
                    ip_str = addr[4][0]
                    resolved_ip = ipaddress.ip_address(ip_str)
                    for blocked in BLOCKED_NETWORKS:
                        if resolved_ip in blocked:
                            return False
            except (socket.gaierror, socket.herror, IndexError, ValueError):
                # DNS resolution failure or unresolvable domain
                pass

        return True
    except Exception:
        return False
