import pytest

from btc_bot.adb import (
    AdbError,
    Device,
    TouchAxes,
    parse_touch_axes,
    parse_touches,
    touch_to_screen,
)

GETEVENT_LP = """\
add device 1: /dev/input/event5
  name:     "gpio-keys"
  events:
    KEY (0001): KEY_VOLUMEDOWN        KEY_VOLUMEUP
add device 2: /dev/input/event3
  name:     "fts_ts"
  events:
    KEY (0001): BTN_TOUCH
    ABS (0003): ABS_MT_SLOT           : value 0, min 0, max 9, fuzz 0, flat 0, resolution 0
                ABS_MT_POSITION_X     : value 0, min 0, max 1263, fuzz 0, flat 0, resolution 0
                ABS_MT_POSITION_Y     : value 0, min 0, max 2779, fuzz 0, flat 0, resolution 0
                ABS_MT_TRACKING_ID    : value 0, min 0, max 65535, fuzz 0, flat 0, resolution 0
"""

GETEVENT_LT = """\
[   5012.100001] /dev/input/event3: EV_ABS       ABS_MT_TRACKING_ID   00000a1b
[   5012.100001] /dev/input/event3: EV_KEY       BTN_TOUCH            DOWN
[   5012.100001] /dev/input/event3: EV_ABS       ABS_MT_POSITION_X    00000100
[   5012.100001] /dev/input/event3: EV_ABS       ABS_MT_POSITION_Y    00000200
[   5012.100001] /dev/input/event3: EV_SYN       SYN_REPORT           00000000
[   5012.150000] /dev/input/event3: EV_ABS       ABS_MT_POSITION_X    00000101
[   5012.150000] /dev/input/event3: EV_SYN       SYN_REPORT           00000000
[   5012.180000] /dev/input/event5: EV_KEY       KEY_VOLUMEUP         DOWN
[   5012.180000] /dev/input/event5: EV_SYN       SYN_REPORT           00000000
[   5012.200000] /dev/input/event3: EV_ABS       ABS_MT_TRACKING_ID   ffffffff
[   5012.200000] /dev/input/event3: EV_KEY       BTN_TOUCH            UP
[   5012.200000] /dev/input/event3: EV_SYN       SYN_REPORT           00000000
"""


def test_parse_touch_axes_finds_touchscreen():
    axes = parse_touch_axes(GETEVENT_LP)
    assert axes == TouchAxes("/dev/input/event3", 1263, 2779)


def test_parse_touches_down_and_up():
    events = list(parse_touches(iter(GETEVENT_LT.splitlines()), "/dev/input/event3"))
    assert [e.kind for e in events] == ["down", "up"]
    assert (events[0].raw_x, events[0].raw_y) == (0x100, 0x200)
    assert events[1].raw_x == 0x101


def test_touch_mapping_landscape():
    axes = TouchAxes("/dev/input/event3", 1263, 2779)
    # Портретный сенсор 1264x2780, экран повёрнут на 90°: скриншот 2780x1264.
    # Верхний левый угол сенсора -> левый нижний угол скриншота.
    assert touch_to_screen(0, 0, axes, 2780, 1264, 1) == (0, 1264)
    assert touch_to_screen(0, 2779, axes, 2780, 1264, 1) == (2779, 1264)
    assert touch_to_screen(1263, 0, axes, 2780, 1264, 1) == (0, 1)
    # Поворот на 270° — зеркально
    assert touch_to_screen(0, 0, axes, 2780, 1264, 3) == (2780, 0)
    # Без поворота координаты совпадают
    assert touch_to_screen(632, 1390, axes, 1264, 2780, 0) == (632, 1390)


def device_with(listing: str, serial: str | None = None) -> Device:
    device = Device(serial=serial)
    device._run = lambda *args, **kw: listing.encode()
    return device


def test_ensure_ready_unauthorized_explains_what_to_do():
    device = device_with("List of devices attached\nf7f494c3\tunauthorized\n\n")
    with pytest.raises(AdbError, match="Разрешить"):
        device.ensure_ready()


def test_ensure_ready_no_permissions_points_to_udev():
    listing = ("List of devices attached\nf7f494c3\tno permissions (missing udev rules?); "
               "see [http://developer.android.com/tools/device.html]\n")
    with pytest.raises(AdbError, match="udev"):
        device_with(listing).ensure_ready()


def test_ensure_ready_picks_single_device_and_requires_serial_for_many():
    assert device_with("List of devices attached\nABC\tdevice\n").ensure_ready() == "ABC"
    many = "List of devices attached\nABC\tdevice\nXYZ\tdevice\n"
    with pytest.raises(AdbError, match="--serial"):
        device_with(many).ensure_ready()
    assert device_with(many, serial="XYZ").ensure_ready() == "XYZ"


def test_ensure_ready_without_devices():
    with pytest.raises(AdbError, match="не виден"):
        device_with("List of devices attached\n\n").ensure_ready()
