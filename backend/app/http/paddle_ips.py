from __future__ import annotations

import ipaddress
import time

import httpx

PADDLE_IPS_URL = "https://api.paddle.com/ips"
_CACHE_TTL_SECONDS = 3600
_cached_cidrs: list[str] | None = None
_cached_at = 0.0


def fetch_paddle_ipv4_cidrs() -> list[str]:
    global _cached_cidrs, _cached_at
    now = time.monotonic()
    if _cached_cidrs is not None and (now - _cached_at) < _CACHE_TTL_SECONDS:
        return _cached_cidrs
    try:
        with httpx.Client(timeout=5.0) as client:
            response = client.get(PADDLE_IPS_URL)
        response.raise_for_status()
        payload = response.json()
        data = payload.get("data") or payload
        cidrs = [str(item) for item in (data.get("ipv4_cidrs") or []) if item]
    except Exception:  # noqa: BLE001
        return list(_cached_cidrs or [])
    _cached_cidrs = cidrs
    _cached_at = now
    return cidrs


def source_ip_from_request(forwarded_for: str | None) -> str | None:
    if not forwarded_for:
        return None
    return forwarded_for.split(",")[0].strip() or None


def ip_in_cidrs(ip: str, cidrs: list[str]) -> bool:
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        return False
    for cidr in cidrs:
        try:
            if addr in ipaddress.ip_network(cidr, strict=False):
                return True
        except ValueError:
            continue
    return False
