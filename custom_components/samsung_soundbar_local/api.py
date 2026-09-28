"""Blocking OCF/DTLS-PSK client for a Samsung soundbar.

Wraps a single ``smartthings_local`` DTLS session. The soundbar accepts only
one DTLS peer at a time, so this owns exactly one session and serializes every
request behind a lock. All methods here are blocking; the HA layer runs them in
the executor.
"""
from __future__ import annotations

import logging
import socket
import struct
import threading
from collections.abc import Callable
from time import monotonic
from uuid import UUID

import cbor2
from smartthings_local.protocol.auth import PskAuth
from smartthings_local.protocol.dtls_session import DtlsCoapSession

try:  # transient per-request timeout, distinct from a dead connection
    from smartthings_local.errors import SessionTimeoutError
except Exception:  # noqa: BLE001 - never fail import over an optional name
    class SessionTimeoutError(Exception):  # type: ignore[no-redef]
        """Fallback if the library doesn't export it."""

from .const import PLAINTEXT_COAP_PORT

# The soundbar accepts a single DTLS peer. Never reconnect more often than this;
# a reconnect-per-failed-request storm jams the device for every client.
_RECONNECT_COOLDOWN_S = 30.0
_REQUEST_TIMEOUT_S = 6.0

_LOGGER = logging.getLogger(__name__)


class SoundbarError(Exception):
    """A request to the soundbar failed."""


def _segs(href: str) -> list[str]:
    return [p for p in href.strip("/").split("/") if p]


class SoundbarClient:
    """One serialized DTLS-PSK session to the soundbar."""

    def __init__(
        self,
        host: str,
        port: int,
        psk_identity: str,
        psk_key: str,
        on_notification: Callable[[str, dict], None] | None = None,
    ) -> None:
        self._host = host
        self._port = port
        self._identity = UUID(psk_identity).bytes
        self._key = bytes.fromhex(psk_key)
        self._lock = threading.Lock()
        self._sess: DtlsCoapSession | None = None
        self._notify_cb = on_notification
        # hrefs the caller wants OBSERVE relations on, and those active on the
        # current session (cleared whenever the session is dropped).
        self._observe_hrefs: set[str] = set()
        self._subscribed: set[str] = set()
        # Rate-limit reconnects so a run of failures can never storm the device.
        self._last_connect_attempt = float("-inf")

    def set_notification_handler(self, cb: Callable[[str, dict], None]) -> None:
        self._notify_cb = cb

    # -- lifecycle -------------------------------------------------------
    def _ensure_connected_locked(self) -> None:
        """Open one session if none is live, at most once per cooldown.

        The cooldown is the storm guard: after a connection-level failure we
        refuse to reconnect again for a while, so a bad run raises quickly
        instead of firing a burst of handshakes at a one-peer device.
        """
        if self._sess is not None:
            return
        since = monotonic() - self._last_connect_attempt
        if since < _RECONNECT_COOLDOWN_S:
            raise SoundbarError(
                f"reconnect on cooldown ({_RECONNECT_COOLDOWN_S - since:.0f}s left)"
            )
        self._last_connect_attempt = monotonic()
        try:
            self._open_locked()
        except Exception as err:  # noqa: BLE001
            # A reboot can move the secure port; try once at the new one.
            if self._rediscover_port():
                self._open_locked()
            else:
                raise SoundbarError(f"connect failed: {err}") from err

    def _open_locked(self) -> None:
        auth = PskAuth(identity=self._identity, key=self._key)
        sess = DtlsCoapSession(self._host, self._port, auth=auth,
                               on_notification=self._dispatch_notification)
        sess.connect()
        sess.start_reader()
        self._sess = sess
        _LOGGER.debug("connected DTLS session to %s:%s", self._host, self._port)
        # A fresh session has no OBSERVE relations — re-register every one.
        self._subscribed.clear()
        self._resubscribe_locked()

    def _drop_locked(self) -> None:
        if self._sess is not None:
            try:
                self._sess.close()
            except Exception:  # noqa: BLE001 - closing best effort
                pass
            self._sess = None
        self._subscribed.clear()

    # -- OBSERVE ---------------------------------------------------------
    def _dispatch_notification(self, href: str, payload: bytes) -> None:
        """Reader-thread callback: decode and hand up to the coordinator."""
        if self._notify_cb is None:
            return
        try:
            rep = cbor2.loads(payload) if payload else {}
        except Exception as err:  # noqa: BLE001
            _LOGGER.debug("bad notification payload on %s: %s", href, err)
            return
        if isinstance(rep, dict):
            try:
                self._notify_cb(href, rep)
            except Exception as err:  # noqa: BLE001
                _LOGGER.debug("notify handler error on %s: %s", href, err)

    def _resubscribe_locked(self) -> None:
        if self._sess is None:
            return
        for href in self._observe_hrefs - self._subscribed:
            try:
                self._sess.subscribe(_segs(href))
                self._subscribed.add(href)
            except Exception as err:  # noqa: BLE001
                _LOGGER.debug("subscribe %s failed: %s", href, err)

    def observe(self, hrefs: list[str]) -> None:
        """Request OBSERVE relations; (re)subscribes on the live session."""
        with self._lock:
            self._observe_hrefs.update(hrefs)
            try:
                self._ensure_connected_locked()
                self._resubscribe_locked()
            except Exception as err:  # noqa: BLE001
                _LOGGER.debug("observe setup deferred: %s", err)

    def close(self) -> None:
        with self._lock:
            self._drop_locked()

    # -- port rediscovery ------------------------------------------------
    def _rediscover_port(self) -> bool:
        """Ask plaintext CoAP /oic/res for the current secure port."""
        try:
            new_port = _read_secure_port(self._host)
        except Exception as err:  # noqa: BLE001
            _LOGGER.debug("port rediscovery failed: %s", err)
            return False
        if new_port and new_port != self._port:
            _LOGGER.info("soundbar secure port moved %s -> %s", self._port, new_port)
            self._port = new_port
            return True
        return new_port is not None

    # -- requests --------------------------------------------------------
    def get(self, href: str) -> dict:
        with self._lock:
            return self._request_locked("get", href, None)

    def post(self, href: str, payload: dict) -> dict:
        with self._lock:
            return self._request_locked("post", href, payload)

    def _request_locked(self, verb: str, href: str, payload: dict | None) -> dict:
        self._ensure_connected_locked()
        sess = self._sess
        if sess is None:  # cooldown declined to open one
            raise SoundbarError(f"{verb} {href}: no session")

        def _do() -> dict:
            if verb == "get":
                _code, body = sess.get(_segs(href), timeout=_REQUEST_TIMEOUT_S)
            else:
                _code, body = sess.post(
                    _segs(href), cbor2.dumps(payload), timeout=_REQUEST_TIMEOUT_S
                )
            decoded = cbor2.loads(body) if body else {}
            return decoded if isinstance(decoded, dict) else {"_value": decoded}

        try:
            return _do()
        except SessionTimeoutError as err:
            # A missed response is NOT a dead connection. Retry once on the
            # SAME session and keep it open — reconnecting on every timeout is
            # exactly what stormed this one-peer device. If it times out again,
            # report failure but leave the session for the next request/push.
            _LOGGER.debug("%s %s timed out; retrying on same session", verb, href)
            try:
                return _do()
            except Exception as err2:  # noqa: BLE001
                raise SoundbarError(f"{verb} {href} timed out") from err2
        except Exception as err:  # noqa: BLE001 - connection-level failure
            # The session looks broken: drop it so the next call can reconnect,
            # but the cooldown bounds how often that actually happens.
            _LOGGER.debug("%s %s failed (%s); dropping session", verb, href, err)
            self._drop_locked()
            raise SoundbarError(f"{verb} {href} failed: {err}") from err


# --- minimal plaintext CoAP GET /oic/res to find the secure port ---------
def _read_secure_port(host: str, timeout: float = 3.0) -> int | None:
    """Return the coaps secure port advertised in /oic/res, or None."""
    import secrets

    def option(delta: int, value: bytes) -> bytes:
        def split(n: int):
            if n < 13:
                return n, b""
            if n < 269:
                return 13, bytes([n - 13])
            return 14, struct.pack("!H", n - 269)
        dn, de = split(delta)
        ln, le = split(len(value))
        return bytes([(dn << 4) | ln]) + de + le + value

    token = secrets.token_bytes(4)
    header = struct.pack("!BBH", (1 << 6) | (0 << 4) | len(token), 1, secrets.randbelow(65536))
    opts = option(11, b"oic") + option(0, b"res") + option(17 - 11, bytes([60]))
    datagram = header + token + opts

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(timeout)
    try:
        collected = bytearray()
        block = 0
        for _ in range(32):
            sock.sendto(datagram, (host, PLAINTEXT_COAP_PORT))
            data, _src = sock.recvfrom(8192)
            # parse options for block2 + payload
            first = data[0]
            off = 4 + (first & 0x0F)
            num = 0
            more = False
            payload = b""
            while off < len(data) and data[off] != 0xFF:
                b = data[off]; off += 1
                d, ln = b >> 4, b & 0x0F
                if d == 13:
                    d = data[off] + 13; off += 1
                elif d == 14:
                    d = struct.unpack("!H", data[off:off+2])[0] + 269; off += 2
                if ln == 13:
                    ln = data[off] + 13; off += 1
                elif ln == 14:
                    ln = struct.unpack("!H", data[off:off+2])[0] + 269; off += 2
                num += d
                if num == 23:  # block2
                    packed = int.from_bytes(data[off:off+ln], "big")
                    more = bool(packed & 0x08)
                off += ln
            if off < len(data):
                payload = data[off+1:]
            collected += payload
            if not more:
                break
            block += 1
            # request next block: rebuild with block2 option
            b2 = ((block << 4) | 6)
            opts2 = option(11, b"oic") + option(0, b"res") + option(17 - 11, bytes([60])) \
                + option(23 - 17, b2.to_bytes(1 if b2 < 0x100 else 2, "big"))
            datagram = header + token + opts2
        rep = cbor2.loads(bytes(collected))
    except Exception:
        return None
    finally:
        sock.close()

    # Walk links for a secure port (legacy p.sec/p.port or eps coaps://).
    found: list[int] = []

    def walk(node):
        if isinstance(node, dict):
            p = node.get("p")
            if isinstance(p, dict) and p.get("sec") and isinstance(p.get("port"), int):
                found.append(p["port"])
            for ep in node.get("eps") or ():
                s = ep.get("ep") if isinstance(ep, dict) else None
                if isinstance(s, str) and s.startswith("coaps://"):
                    try:
                        found.append(int(s.rsplit(":", 1)[1]))
                    except ValueError:
                        pass
            for v in node.values():
                walk(v)
        elif isinstance(node, (list, tuple)):
            for it in node:
                walk(it)

    walk(rep)
    return found[0] if found else None
