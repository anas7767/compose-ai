from __future__ import annotations

import socket
import ssl
from urllib.parse import urlparse

from compose_ai_api.core.config import get_settings


async def check_redis_connection() -> bool:
    settings = get_settings()
    parsed = urlparse(settings.redis_url)
    host = parsed.hostname
    port = parsed.port or 6379
    if not host or parsed.scheme not in {"redis", "rediss"}:
        return False

    try:
        raw_socket = socket.create_connection((host, port), timeout=2)
        with raw_socket:
            connection: socket.socket | ssl.SSLSocket
            if parsed.scheme == "rediss":
                context = ssl.create_default_context()
                connection = context.wrap_socket(raw_socket, server_hostname=host)
            else:
                connection = raw_socket
            connection.settimeout(2)
            password = parsed.password
            if password:
                response = _send_command(connection, "AUTH", password)
                if not response.startswith("+OK"):
                    return False
            if parsed.path and parsed.path != "/":
                database = parsed.path.lstrip("/")
                response = _send_command(connection, "SELECT", database)
                if not response.startswith("+OK"):
                    return False
            return _send_command(connection, "PING").startswith("+PONG")
    except OSError:
        return False


def _send_command(connection: socket.socket | ssl.SSLSocket, *parts: str) -> str:
    command = f"*{len(parts)}\r\n" + "".join(
        f"${len(part.encode('utf-8'))}\r\n{part}\r\n" for part in parts
    )
    connection.sendall(command.encode("utf-8"))
    return connection.recv(1024).decode("utf-8", errors="replace")
