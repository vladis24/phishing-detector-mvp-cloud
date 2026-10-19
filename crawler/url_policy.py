"""Fail-closed destination policy shared by browser interception and egress proxy."""
import ipaddress
import socket
from urllib.parse import urlsplit


class UnsafeURL(ValueError):
    pass


def public_address(value):
    address = ipaddress.ip_address(value.split("%", 1)[0])
    if getattr(address, "ipv4_mapped", None):
        address = address.ipv4_mapped
    if isinstance(address, ipaddress.IPv6Address) and (
            address.sixtofour is not None or address.teredo is not None or
            address in ipaddress.ip_network("64:ff9b::/96") or
            address in ipaddress.ip_network("64:ff9b:1::/48")):
        return False
    # is_global alone also accepts multicast on some Python versions.
    return (address.is_global and not any((address.is_private, address.is_loopback,
            address.is_link_local, address.is_multicast, address.is_reserved,
            address.is_unspecified, getattr(address, "is_site_local", False))))


def parsed_url(value):
    if not isinstance(value, str):
        raise UnsafeURL("URL must be text")
    value = value.strip()
    if not value or len(value) > 8192 or "\\" in value or any(ord(c) <= 32 or ord(c) == 127 for c in value):
        raise UnsafeURL("Invalid URL characters")
    try:
        parts = urlsplit(value)
        if parts.scheme not in {"http", "https"} or not parts.hostname:
            raise ValueError("HTTP(S) URL required")
        if parts.username is not None or parts.password is not None:
            raise ValueError("Credentials are forbidden")
        host = parts.hostname.rstrip(".").encode("idna").decode("ascii").lower()
        if not host or "%" in host:
            raise ValueError("Invalid hostname")
        port = parts.port if parts.port is not None else (443 if parts.scheme == "https" else 80)
        if not 1 <= port <= 65535:
            raise ValueError("Invalid port")
    except (ValueError, UnicodeError) as exc:
        raise UnsafeURL("Complete HTTP(S) URL without credentials required") from exc
    return value, parts.scheme, host, port


def resolve_destination(value, trusted_origin=None):
    """Validate *all* answers, returning numeric socket addresses to pin connects.

    trusted_origin is created internally for one ephemeral fixture server. In that
    mode every other origin is forbidden, including public internet destinations.
    """
    value, scheme, host, port = parsed_url(value)
    trusted = trusted_origin is not None
    if trusted:
        _, ts, th, tp = parsed_url(trusted_origin)
        if (scheme, host, port) != (ts, th, tp) or host != "127.0.0.1":
            raise UnsafeURL("Request outside trusted fixture origin")
    else:
        validate_public_syntax(value)
    try:
        # getaddrinfo also canonicalizes OS-supported short/hex/integer IPv4.
        answers = socket.getaddrinfo(host, port, socket.AF_UNSPEC, socket.SOCK_STREAM)
    except (OSError, UnicodeError) as exc:
        raise UnsafeURL("DNS resolution failed") from exc
    if not answers:
        raise UnsafeURL("DNS returned no addresses")
    result = []
    for family, kind, proto, _, sockaddr in answers:
        if family not in {socket.AF_INET, socket.AF_INET6}:
            raise UnsafeURL("Unsupported address family")
        if not trusted and not public_address(sockaddr[0]):
            raise UnsafeURL("Non-public destination is forbidden")
        result.append((family, kind, proto, sockaddr))
    return value, result


def validate_public_url(value):
    return resolve_destination(value)[0]


def validate_public_syntax(value):
    """Nonblocking first gate; hostname DNS runs inside the supervised worker."""
    value, _, host, _ = parsed_url(value)
    if host == "localhost" or host.endswith(".localhost"):
        raise UnsafeURL("Localhost is forbidden")
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        try:
            # inet_aton is a parser, not a DNS call; includes OS legacy IPv4 forms.
            address = ipaddress.ip_address(socket.inet_ntoa(socket.inet_aton(host)))
        except OSError:
            return value
    if not public_address(str(address)):
        raise UnsafeURL("Non-public destination is forbidden")
    return value
