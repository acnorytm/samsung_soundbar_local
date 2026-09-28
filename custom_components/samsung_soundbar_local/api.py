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
from uuid import UUID

import cbor2
from smartthings_local.protocol.auth import PskAuth
from smartthings_local.protocol.dtls_session import DtlsCoapSession

from .const import PLAINTEXT_COAP_PORT

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

    def set_notification_handler(self, cb: Callable[[str, dict], None]) -> None:
        self._notify_cb = cb

    # -- lifecycle -------------------------------------------------------
    def _connect_locked(self) -> None:
        if self._sess is not None:
            return
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
                self._connect_locked()
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
        last_err: Exception | None = None
        for attempt in range(2):  # one reconnect retry
            try:
                self._connect_locked()
                assert self._sess is not None
                if verb == "get":
                    code, body = self._sess.get(_segs(href))
                else:
                    code, body = self._sess.post(_segs(href), cbor2.dumps(payload))
                if not str(code).startswith("6") and not str(code).startswith("2"):
                    # smartthings-local returns int CoAP codes: 69=2.05, 68=2.04
                    pass
                decoded = cbor2.loads(body) if body else {}
                if not isinstance(decoded, dict):
                    decoded = {"_value": decoded}
                return decoded
            except Exception as err:  # noqa: BLE001
                last_err = err
                _LOGGER.debug("%s %s failed (attempt %d): %s", verb, href, attempt, err)
                self._drop_locked()
                if attempt == 0:
                    self._rediscover_port()
        raise SoundbarError(f"{verb} {href} failed: {last_err}") from last_err


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
