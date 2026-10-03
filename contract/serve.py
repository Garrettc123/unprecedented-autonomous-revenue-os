"""Process entrypoint: serve contract.app on $PORT, dual-stack (IPv4 + IPv6).

uvicorn's ``--host ::`` creates an IPv6-only socket (asyncio sets IPV6_V6ONLY),
so we bind the socket ourselves with IPV6_V6ONLY=0. That is reachable over
Railway private networking (incl. legacy IPv6-only environments) and over IPv4.
Set HOST=0.0.0.0 to force IPv4-only; falls back to IPv4 if IPv6 is unavailable.
"""
from __future__ import annotations

import logging
import os
import socket

import uvicorn

logger = logging.getLogger("garcar.serve")


def make_socket(host: str, port: int) -> socket.socket:
    if host in ("::", "") and socket.has_ipv6:
        try:
            sock = socket.socket(socket.AF_INET6, socket.SOCK_STREAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 0)
            sock.bind(("::", port))
            return sock
        except OSError as exc:
            logger.warning("IPv6 bind failed (%s); falling back to 0.0.0.0", exc)
            host = "0.0.0.0"
    family = socket.AF_INET6 if ":" in host else socket.AF_INET
    sock = socket.socket(family, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind((host, port))
    return sock


def main() -> None:
    host = os.getenv("HOST", "::")
    port = int(os.getenv("PORT", "8080"))
    sock = make_socket(host, port)
    config = uvicorn.Config("contract.app:app", log_level=os.getenv("LOG_LEVEL", "info"))
    uvicorn.Server(config).run(sockets=[sock])


if __name__ == "__main__":
    main()
