"""Распознавание: нормализация кадра и поиск шаблонов.

Все координаты в проекте записаны в «рабочем» пространстве: кадр
масштабируется до ширины 1280 px с сохранением пропорций. Для телефона
2780×1264 это 1280×582, ровно как у скриншотов из Telegram. Поэтому
шаблоны, вырезанные из сжатых скриншотов, подходят и для живого экрана.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from . import imaging

WORK_WIDTH = 1280
DEFAULT_THRESHOLD = 0.75
DEFAULT_MARGIN = 40

PROJECT_ROOT = Path(__file__).resolve().parent.parent
TEMPLATES_DIR = PROJECT_ROOT / "templates"
MANIFEST_NAME = "manifest.json"


def normalize(frame: np.ndarray) -> tuple[np.ndarray, float]:
    """Приводит кадр к ширине WORK_WIDTH.

    Возвращает (кадр, scale), где scale переводит рабочие координаты
    в координаты устройства: device = work * scale.
    """
    h, w = frame.shape[:2]
    if w == WORK_WIDTH:
        return frame, 1.0
    scale = w / WORK_WIDTH
    return imaging.resize(frame, WORK_WIDTH, max(1, round(h / scale))), scale


def load_image(path: str | Path) -> np.ndarray:
    # чтение байтов + decode: imread на Windows не открывает пути с кириллицей
    img = imaging.decode(Path(path).read_bytes())
    if img is None:
        raise ValueError(f"Не удалось прочитать изображение: {path}")
    return img


def save_image(path: str | Path, img: np.ndarray, jpeg_quality: int = 92) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(imaging.encode(img, path.suffix, jpeg_quality))


@dataclass
class Match:
    name: str
    score: float
    box: tuple[int, int, int, int]  # x1, y1, x2, y2 в рабочих координатах
    brightness: float = 1.0  # яркость найденного места относительно шаблона

    @property
    def center(self) -> tuple[int, int]:
        x1, y1, x2, y2 = self.box
        return (x1 + x2) // 2, (y1 + y2) // 2


@dataclass
class Template:
    name: str
    image: np.ndarray
    box: tuple[int, int, int, int]
    threshold: float = DEFAULT_THRESHOLD
    margin: int = DEFAULT_MARGIN
    # Совпадение по форме не учитывает яркость, а всплывающие окна затемняют
    # всё под собой. Для кнопок требуем «незатемнённость», чтобы не нажать
    # на кнопку карты сквозь чужое окно.
    min_brightness: float = 0.0
    source: str | None = None
    note: str = ""

    def search_area(self, frame_shape: tuple[int, ...]) -> tuple[int, int, int, int]:
        h, w = frame_shape[:2]
        x1, y1, x2, y2 = self.box
        m = self.margin
        return max(0, x1 - m), max(0, y1 - m), min(w, x2 + m), min(h, y2 + m)

    def match(self, frame: np.ndarray) -> Match:
        """Ищет шаблон в окрестности его штатного места на кадре."""
        ax1, ay1, ax2, ay2 = self.search_area(frame.shape)
        th, tw = self.image.shape[:2]
        if ax2 - ax1 < tw or ay2 - ay1 < th:
            return Match(self.name, 0.0, self.box)
        roi = frame[ay1:ay2, ax1:ax2]
        score, (lx, ly) = imaging.match_template(roi, self.image)
        x1, y1 = ax1 + lx, ay1 + ly
        found = frame[y1:y1 + th, x1:x1 + tw]
        brightness = float(found.mean()) / max(float(self.image.mean()), 1.0)
        return Match(self.name, score, (x1, y1, x1 + tw, y1 + th), brightness)


@dataclass
class TemplateLibrary:
    directory: Path
    templates: dict[str, Template] = field(default_factory=dict)

    @classmethod
    def load(cls, directory: str | Path = TEMPLATES_DIR) -> "TemplateLibrary":
        directory = Path(directory)
        lib = cls(directory)
        for name, meta in read_manifest(directory).items():
            png = directory / f"{name}.png"
            if not png.exists():
                continue
            lib.templates[name] = Template(
                name=name,
                image=load_image(png),
                box=tuple(meta["box"]),
                threshold=float(meta.get("threshold", DEFAULT_THRESHOLD)),
                margin=int(meta.get("margin", DEFAULT_MARGIN)),
                min_brightness=float(meta.get("min_brightness", 0.0)),
                source=meta.get("source"),
                note=meta.get("note", ""),
            )
        return lib

    def __contains__(self, name: str) -> bool:
        return name in self.templates

    def match(self, frame: np.ndarray, name: str) -> Match | None:
        tpl = self.templates.get(name)
        return tpl.match(frame) if tpl else None

    def found(self, frame: np.ndarray, name: str) -> Match | None:
        """Совпадение, если оценка и яркость не ниже порогов шаблона, иначе None."""
        m = self.match(frame, name)
        if m is None:
            return None
        tpl = self.templates[name]
        if m.score < tpl.threshold or m.brightness < tpl.min_brightness:
            return None
        return m


def read_manifest(directory: str | Path = TEMPLATES_DIR) -> dict[str, dict]:
    path = Path(directory) / MANIFEST_NAME
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def write_manifest(manifest: dict[str, dict], directory: str | Path = TEMPLATES_DIR) -> None:
    path = Path(directory) / MANIFEST_NAME
    path.parent.mkdir(parents=True, exist_ok=True)
    # по шаблону на строку, чтобы правки в git читались легко
    names = sorted(manifest)
    lines = [
        f"  {json.dumps(name, ensure_ascii=False)}: "
        f"{json.dumps(manifest[name], ensure_ascii=False, sort_keys=True)}"
        for name in names
    ]
    path.write_text("{\n" + ",\n".join(lines) + "\n}\n", encoding="utf-8")


def crop_template(
    image_path: str | Path,
    box: tuple[int, int, int, int],
    name: str,
    directory: str | Path = TEMPLATES_DIR,
    threshold: float | None = None,
    note: str | None = None,
) -> Path:
    """Вырезает шаблон из скриншота любого разрешения и вносит его в манифест.

    box задаётся в рабочих координатах (кадр шириной 1280).
    """
    directory = Path(directory)
    frame, _ = normalize(load_image(image_path))
    x1, y1, x2, y2 = box
    h, w = frame.shape[:2]
    if not (0 <= x1 < x2 <= w and 0 <= y1 < y2 <= h):
        raise ValueError(f"Рамка {box} выходит за кадр {w}x{h}")
    out = directory / f"{name}.png"
    save_image(out, frame[y1:y2, x1:x2])

    manifest = read_manifest(directory)
    entry = manifest.get(name, {})
    entry["box"] = [x1, y1, x2, y2]
    entry["source"] = _relative_source(image_path)
    if threshold is not None:
        entry["threshold"] = threshold
    if note is not None:
        entry["note"] = note
    manifest[name] = entry
    write_manifest(manifest, directory)
    return out


def rebuild_templates(directory: str | Path = TEMPLATES_DIR) -> list[str]:
    """Заново вырезает все шаблоны из исходных скриншотов, указанных в манифесте.

    Если положить на место исходника скриншот того же экрана в полном
    разрешении (с тем же именем, расширение любое), шаблон станет точнее.
    """
    directory = Path(directory)
    rebuilt = []
    for name, meta in read_manifest(directory).items():
        src = meta.get("source")
        if not src:
            continue
        path = _find_source(src)
        if path is None:
            continue
        crop_template(path, tuple(meta["box"]), name, directory)
        rebuilt.append(name)
    return rebuilt


def _relative_source(path: str | Path) -> str:
    path = Path(path).resolve()
    try:
        return path.relative_to(PROJECT_ROOT).as_posix()
    except ValueError:
        return str(path)


def _find_source(src: str) -> Path | None:
    path = Path(src)
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    # Рядом с исходником может лежать тот же экран в другом формате
    # (например, .png в полном разрешении). Берём самый крупный по ширине.
    candidates = [p for p in path.parent.glob(path.stem + ".*") if p.is_file()]
    if not candidates:
        return None
    return max(candidates, key=_image_width)


def _image_width(path: Path) -> int:
    try:
        return load_image(path).shape[1]
    except ValueError:
        return -1
