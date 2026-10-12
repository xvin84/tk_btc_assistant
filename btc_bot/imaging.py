"""Работа с изображениями: OpenCV, а если его нет — numpy + Pillow.

На компьютере стоит OpenCV. В Termux он тянет ffmpeg и Qt6 и часто не
ставится, поэтому там те же операции считаются на numpy (поиск шаблона
через БПФ) и Pillow (уменьшение кадра, чтение и запись файлов).
Результаты совпадают с OpenCV с точностью до сотых.

Выбрать реализацию явно: переменная окружения BTC_BOT_IMAGING=opencv|numpy.
"""

from __future__ import annotations

import io
import os

import numpy as np

_choice = os.environ.get("BTC_BOT_IMAGING", "").lower()
cv2 = None
if _choice != "numpy":
    try:
        import cv2  # type: ignore[no-redef]
    except ImportError:
        if _choice == "opencv":
            raise

BACKEND = "opencv" if cv2 is not None else "numpy"

if cv2 is None:
    from PIL import Image, ImageDraw


# --- файлы --------------------------------------------------------------

def decode(data: bytes) -> np.ndarray | None:
    """PNG/JPEG из памяти -> BGR uint8 (или None, если не картинка)."""
    if cv2 is not None:
        return cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)
    try:
        with Image.open(io.BytesIO(data)) as img:
            rgb = np.asarray(img.convert("RGB"))
    except (OSError, ValueError):
        return None
    return np.ascontiguousarray(rgb[:, :, ::-1])


def encode(img: np.ndarray, ext: str, jpeg_quality: int = 92) -> bytes:
    ext = ext.lower()
    if cv2 is not None:
        params = [cv2.IMWRITE_JPEG_QUALITY, jpeg_quality] if ext in (".jpg", ".jpeg") else []
        ok, buf = cv2.imencode(ext, img, params)
        if not ok:
            raise ValueError(f"Не удалось закодировать изображение в {ext}")
        return buf.tobytes()
    fmt = {".jpg": "JPEG", ".jpeg": "JPEG", ".png": "PNG"}.get(ext)
    if fmt is None:
        raise ValueError(f"Неподдерживаемый формат {ext}")
    out = io.BytesIO()
    kwargs = {"quality": jpeg_quality} if fmt == "JPEG" else {}
    Image.fromarray(np.ascontiguousarray(img[:, :, ::-1])).save(out, fmt, **kwargs)
    return out.getvalue()


# --- геометрия ----------------------------------------------------------

def resize(img: np.ndarray, width: int, height: int) -> np.ndarray:
    """Уменьшение усреднением (как INTER_AREA), увеличение — билинейно."""
    if cv2 is not None:
        shrink = img.shape[1] > width
        interp = cv2.INTER_AREA if shrink else cv2.INTER_LINEAR
        return cv2.resize(img, (width, height), interpolation=interp)
    return resize_numpy(img, width, height)


def resize_numpy(img: np.ndarray, width: int, height: int) -> np.ndarray:
    """Pillow: BOX при уменьшении (усреднение, как INTER_AREA), иначе билинейно.

    Порядок каналов (BGR) Pillow не важен: каждый канал масштабируется отдельно.
    """
    from PIL import Image as PILImage

    shrink = img.shape[1] > width
    pil = PILImage.fromarray(np.ascontiguousarray(img))
    resample = PILImage.BOX if shrink else PILImage.BILINEAR
    return np.asarray(pil.resize((width, height), resample)).copy()


def scale_brightness(img: np.ndarray, alpha: float) -> np.ndarray:
    return np.clip(img.astype(np.float32) * alpha, 0, 255).astype(np.uint8)


def draw_circle(img: np.ndarray, center: tuple[int, int], radius: int,
                color: tuple[int, int, int], thickness: int) -> None:
    """Рисует окружность на BGR-изображении на месте (thickness < 0 — залитый круг)."""
    if cv2 is not None:
        cv2.circle(img, center, radius, color, thickness)
        return
    pil = Image.fromarray(np.ascontiguousarray(img[:, :, ::-1]))
    x, y = center
    rgb = tuple(reversed(color))
    box = (x - radius, y - radius, x + radius, y + radius)
    if thickness < 0:
        ImageDraw.Draw(pil).ellipse(box, fill=rgb)
    else:
        ImageDraw.Draw(pil).ellipse(box, outline=rgb, width=thickness)
    img[:] = np.asarray(pil)[:, :, ::-1]


# --- поиск шаблона ------------------------------------------------------

def match_template(image: np.ndarray, templ: np.ndarray) -> tuple[float, tuple[int, int]]:
    """Лучшее совпадение TM_CCOEFF_NORMED: (оценка, (x, y) левого верхнего угла)."""
    if cv2 is not None:
        res = cv2.matchTemplate(image, templ, cv2.TM_CCOEFF_NORMED)
    else:
        res = ccoeff_normed(image, templ)
    res = np.nan_to_num(res, nan=0.0, posinf=0.0, neginf=0.0)
    y, x = np.unravel_index(int(np.argmax(res)), res.shape)
    return float(res[y, x]), (int(x), int(y))


def ccoeff_normed(image: np.ndarray, templ: np.ndarray) -> np.ndarray:
    """TM_CCOEFF_NORMED из OpenCV на numpy.

    Для каждого сдвига: сумма по каналам произведений (I - среднее окна) и
    (T - среднее шаблона), делённая на корень из произведения их энергий.
    Числитель считаем свёрткой через БПФ, энергию окна — интегральными суммами.
    """
    img = np.atleast_3d(image).astype(np.float64)
    tpl = np.atleast_3d(templ).astype(np.float64)
    H, W, C = img.shape
    h, w, _ = tpl.shape
    out_h, out_w = H - h + 1, W - w + 1
    n = h * w
    fshape = (_fast_len(H + h - 1), _fast_len(W + w - 1))

    numerator = np.zeros((out_h, out_w))
    window_energy = np.zeros((out_h, out_w))
    templ_energy = 0.0
    for c in range(C):
        t = tpl[:, :, c] - tpl[:, :, c].mean()
        templ_energy += float((t * t).sum())
        i = img[:, :, c]
        spec = np.fft.rfft2(i, fshape) * np.fft.rfft2(t[::-1, ::-1], fshape)
        full = np.fft.irfft2(spec, fshape)
        numerator += full[h - 1:H, w - 1:W]
        s1 = _window_sum(i, h, w)
        s2 = _window_sum(i * i, h, w)
        window_energy += np.maximum(s2 - s1 * s1 / n, 0.0)

    denom = np.sqrt(templ_energy * window_energy)
    with np.errstate(divide="ignore", invalid="ignore"):
        res = np.where(denom > 1e-6 * max(templ_energy, 1.0), numerator / denom, 0.0)
    return np.clip(res, -1.0, 1.0).astype(np.float32)


def _window_sum(a: np.ndarray, h: int, w: int) -> np.ndarray:
    s = np.zeros((a.shape[0] + 1, a.shape[1] + 1))
    s[1:, 1:] = a.cumsum(0).cumsum(1)
    return s[h:, w:] - s[:-h, w:] - s[h:, :-w] + s[:-h, :-w]


def _fast_len(n: int) -> int:
    """Ближайший сверху размер вида 2^a·3^b·5^c: на нём БПФ быстрый."""
    best = 1 << (n - 1).bit_length()
    p5 = 1
    while p5 < best:
        p35 = p5
        while p35 < best:
            p = p35
            while p < n:
                p *= 2
            best = min(best, p)
            p35 *= 3
        p5 *= 5
    return best
