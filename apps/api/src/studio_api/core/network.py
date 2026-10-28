from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlparse

from studio_api.core.errors import ErrorCode, StudioError


def validate_public_url(url: str) -> str:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise StudioError(ErrorCode.POLICY_REJECTED, "Only HTTP(S) URLs are allowed")
    try:
        addresses = {item[4][0] for item in socket.getaddrinfo(parsed.hostname, parsed.port or 443)}
    except socket.gaierror as exc:
        raise StudioError(ErrorCode.POLICY_REJECTED, "URL host cannot be resolved") from exc
    for value in addresses:
        ip = ipaddress.ip_address(value)
        if not ip.is_global:
            raise StudioError(ErrorCode.POLICY_REJECTED, "Private or local URL is not allowed")
    return url
