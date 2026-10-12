"""Запуск на самом телефоне: сырые скриншоты и подключение adb к себе."""

import struct

import cv2
import numpy as np
import pytest

from btc_bot import adb as adb_mod
from btc_bot.adb import (
    AdbError,
    Device,
    connect_local,
    decode_raw_screencap,
    parse_mdns_ports,
)


def raw_frame(bgr: np.ndarray, fmt: int = 1, header: int = 16) -> bytes:
    h, w = bgr.shape[:2]
    if fmt == 5:
        pixels = np.dstack([bgr, np.full((h, w), 255, np.uint8)])  # BGRA
    else:
        pixels = np.dstack([bgr[:, :, ::-1], np.full((h, w), 255, np.uint8)])  # RGBA
    head = struct.pack("<III", w, h, fmt) + (b"\0" * (header - 12))
    return head + pixels.tobytes()


@pytest.mark.parametrize("fmt,header", [(1, 16), (1, 12), (2, 16), (5, 16)])
def test_decode_raw_screencap(fmt, header):
    rng = np.random.default_rng(0)
    bgr = rng.integers(0, 256, (7, 11, 3), dtype=np.uint8)
    assert np.array_equal(decode_raw_screencap(raw_frame(bgr, fmt, header)), bgr)


def test_decode_raw_screencap_rejects_unknown_format():
    bgr = np.zeros((2, 2, 3), np.uint8)
    with pytest.raises(ValueError):
        decode_raw_screencap(raw_frame(bgr, fmt=43))  # RGBA_1010102
    with pytest.raises(ValueError):
        decode_raw_screencap(raw_frame(bgr)[:-1])


def test_raw_capture_falls_back_to_png():
    bgr = np.full((4, 6, 3), (10, 20, 30), np.uint8)
    png = cv2.imencode(".png", bgr)[1].tobytes()
    device = Device(capture="raw")
    device._run = lambda *args, **kw: png if "-p" in args else b"garbage"
    assert np.array_equal(device.screenshot(), bgr)
    assert device.capture == "png"


def test_parse_mdns_ports():
    text = ("List of discovered mdns services\n"
            "adb-f7f494c3-AbCdEf\t_adb-tls-pairing._tcp\t192.168.1.23:40111\n"
            "adb-f7f494c3-AbCdEf\t_adb-tls-connect._tcp\t192.168.1.23:37555\n")
    assert parse_mdns_ports(text) == [37555]


class FakeAdb:
    """Минимальная модель adb-сервера: какие адреса открыты и подключены."""

    def __init__(self, open_ports, mdns_port=None, authorized=True):
        self.open_ports = set(open_ports)
        self.mdns_port = mdns_port
        self.authorized = authorized
        self.connected: dict[str, str] = {}
        self.calls = []

    def run(self, device, *args, timeout=None, serial=True):
        self.calls.append((device.serial if serial else None,) + args)
        cmd = args[0]
        if cmd == "connect":
            port = int(args[1].rsplit(":", 1)[1])
            if port not in self.open_ports:
                raise AdbError("failed to connect")
            self.connected[args[1]] = "device" if self.authorized else "unauthorized"
            return f"connected to {args[1]}".encode()
        if cmd == "devices":
            rows = "".join(f"{a}\t{s}\n" for a, s in self.connected.items())
            return ("List of devices attached\n" + rows).encode()
        if cmd == "mdns":
            if self.mdns_port is None:
                return b"List of discovered mdns services\n"
            return (f"List of discovered mdns services\nadb-x\t_adb-tls-connect._tcp\t"
                    f"10.0.0.5:{self.mdns_port}\n").encode()
        if cmd == "tcpip":
            self.open_ports.add(int(args[1]))
            return b"restarting in TCP mode port: 5555\n"
        raise AssertionError(f"неожиданная команда {args}")


@pytest.fixture
def fake_adb(monkeypatch):
    def install(**kw):
        fake = FakeAdb(**kw)
        monkeypatch.setattr(adb_mod.Device, "_run",
                            lambda self, *a, **k: fake.run(self, *a, **k))
        return fake
    return install


def test_connect_local_uses_open_tcp_port(fake_adb):
    fake = fake_adb(open_ports={5555})
    assert connect_local(sleep=lambda s: None) == "127.0.0.1:5555"
    assert not any(c[1] == "tcpip" for c in fake.calls)


def test_connect_local_switches_wireless_debugging_to_tcp(fake_adb):
    fake = fake_adb(open_ports={37555}, mdns_port=37555)
    assert connect_local(sleep=lambda s: None) == "127.0.0.1:5555"
    assert ("127.0.0.1:37555", "tcpip", "5555") in fake.calls


def test_connect_local_with_explicit_port(fake_adb):
    fake_adb(open_ports={41000})
    assert connect_local(wireless_port=41000, sleep=lambda s: None) == "127.0.0.1:5555"


def test_connect_local_explains_options_when_nothing_works(fake_adb):
    fake_adb(open_ports=set())
    with pytest.raises(AdbError, match="adb tcpip 5555"):
        connect_local(sleep=lambda s: None)


def test_connect_local_waits_for_authorization_then_gives_up(fake_adb):
    fake_adb(open_ports={5555}, authorized=False)
    waits = []
    with pytest.raises(AdbError):
        connect_local(sleep=waits.append, auth_wait=10)
    assert sum(waits) >= 10


def test_ensure_ready_reconnects_network_serial(fake_adb):
    fake = fake_adb(open_ports={5555})
    assert Device(serial="127.0.0.1:5555").ensure_ready() == "127.0.0.1:5555"
    assert (None, "connect", "127.0.0.1:5555") in fake.calls


def test_launch_brings_game_to_front():
    device = Device()
    sent = []
    device.shell = lambda cmd, timeout=None: sent.append(cmd) or ""
    device.launch("com.funcat.tgbtc")
    assert sent == ["monkey -p com.funcat.tgbtc -c android.intent.category.LAUNCHER 1"]
