"""Запасной режим без OpenCV (Termux) должен давать те же оценки, что и OpenCV."""

import numpy as np
import pytest

from btc_bot import imaging
from btc_bot.vision import TemplateLibrary, normalize

from conftest import SAMPLES, as_device_frame, sample

cv2 = pytest.importorskip("cv2")


@pytest.fixture(scope="module")
def frames():
    return {p.stem: normalize(sample(p.stem))[0] for p in sorted(SAMPLES.glob("*.jpg"))}


def test_ccoeff_normed_matches_opencv(frames):
    lib = TemplateLibrary.load()
    worst = 0.0
    for frame in frames.values():
        for tpl in lib.templates.values():
            x1, y1, x2, y2 = tpl.search_area(frame.shape)
            roi = frame[y1:y2, x1:x2]
            expected = cv2.matchTemplate(roi, tpl.image, cv2.TM_CCOEFF_NORMED)
            got = imaging.ccoeff_normed(roi, tpl.image)
            assert got.shape == expected.shape
            worst = max(worst, float(np.abs(got - expected).max()))
            assert np.unravel_index(got.argmax(), got.shape) == \
                np.unravel_index(expected.argmax(), expected.shape)
    assert worst < 1e-3


def test_resize_gives_same_template_scores_as_opencv():
    # Пиксели на резких краях чуть отличаются, но для распознавания важны оценки
    lib = TemplateLibrary.load()
    worst = 0.0
    for path in sorted(SAMPLES.glob("*.jpg")):
        full = as_device_frame(sample(path.stem))
        expected = cv2.resize(full, (1280, 582), interpolation=cv2.INTER_AREA)
        got = imaging.resize_numpy(full, 1280, 582)
        assert got.shape == expected.shape
        assert np.abs(got.astype(int) - expected.astype(int)).mean() < 2
        for tpl in lib.templates.values():
            worst = max(worst, abs(tpl.match(got).score - tpl.match(expected).score))
    assert worst < 0.03


def test_encode_decode_roundtrip():
    img = sample("victory")
    assert np.array_equal(imaging.decode(imaging.encode(img, ".png")), img)
    assert imaging.decode(b"not an image") is None
