import ipaddress
import os
from typing import Optional
from fastapi import Request


def get_trusted_proxies() -> list[str]:
    raw = os.getenv("TRUSTED_PROXIES", "")
    if not raw.strip():
        return ["127.0.0.1", "::1"]
    return [p.strip() for p in raw.split(",") if p.strip()]


def is_ip_trusted(peer_ip: str, trusted_list: list[str]) -> bool:
    if not peer_ip:
        return False
    if "*" in trusted_list:
        return True
    try:
        peer_addr = ipaddress.ip_address(peer_ip)
        for trusted in trusted_list:
            try:
                if "/" in trusted:
                    if peer_addr in ipaddress.ip_network(trusted, strict=False):
                        return True
                elif peer_addr == ipaddress.ip_address(trusted):
                    return True
            except ValueError:
                if peer_ip == trusted:
                    return True
    except ValueError:
        return peer_ip in trusted_list
    return False


def get_client_ip(request: Request) -> str:
    """
    Safely determine the client IP address.
    Only respects X-Forwarded-For if the direct peer IP is in TRUSTED_PROXIES.
    """
    peer_ip = request.client.host if request.client else "127.0.0.1"
    trusted_proxies = get_trusted_proxies()

    if is_ip_trusted(peer_ip, trusted_proxies):
        xff = request.headers.get("X-Forwarded-For")
        if xff:
            # First IP in X-Forwarded-For is the original client
            client_ip = xff.split(",")[0].strip()
            if client_ip:
                return client_ip

    return peer_ip
