"""SVG-иконки интерфейса: тонкие линии 24x24, цвет подставляется при отрисовке."""

from __future__ import annotations

from PySide6.QtCore import QByteArray, QRectF, Qt
from PySide6.QtGui import QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer

from .theme import ACCENT

_WRAP = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" '
    'stroke="currentColor" stroke-width="1.8" stroke-linecap="round" '
    'stroke-linejoin="round">{body}</svg>'
)

_BODIES: dict[str, str] = {
    "phone": '<rect x="7" y="2.5" width="10" height="19" rx="2"/><path d="M11 18.5h2"/>',
    "sliders": '<path d="M4 6h16M4 12h16M4 18h16"/>'
               '<circle cx="9" cy="6" r="2.2"/><circle cx="15" cy="12" r="2.2"/>'
               '<circle cx="7" cy="18" r="2.2"/>',
    "list": '<path d="M9 6h11M9 12h11M9 18h11"/>'
            '<circle cx="4.5" cy="6" r="1" fill="currentColor" stroke="none"/>'
            '<circle cx="4.5" cy="12" r="1" fill="currentColor" stroke="none"/>'
            '<circle cx="4.5" cy="18" r="1" fill="currentColor" stroke="none"/>',
    "help": '<circle cx="12" cy="12" r="9"/>'
            '<path d="M9.5 9.5a2.5 2.5 0 1 1 3.5 2.3c-.6.3-1 .8-1 1.5v.7"/>'
            '<circle cx="12" cy="17" r=".9" fill="currentColor" stroke="none"/>',
    "refresh": '<path d="M22 4v6h-6"/><path d="M20.5 15a8.5 8.5 0 1 1-2-8.5L22 10"/>',
    "download": '<path d="M12 4v11M7.5 10.5 12 15l4.5-4.5M5 19.5h14"/>',
    "folder": '<path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5'
              'a2 2 0 0 1-2-2z"/>',
    "link": '<path d="M10 14a4 4 0 0 0 5.7 0l3-3a4 4 0 0 0-5.7-5.7l-1 1"/>'
            '<path d="M14 10a4 4 0 0 0-5.7 0l-3 3a4 4 0 0 0 5.7 5.7l1-1"/>',
    "chain": '<rect x="2.5" y="8.5" width="9" height="7" rx="3.5"/>'
             '<rect x="12.5" y="8.5" width="9" height="7" rx="3.5"/><path d="M9 12h6"/>',
}


def icon(name: str, color: str = "#8a8f98", selected_color: str = ACCENT) -> QIcon:
    """QIcon из встроенного SVG: обычное состояние и выделенное (акцент)."""
    result = QIcon()
    result.addPixmap(_render(name, color), QIcon.Mode.Normal)
    result.addPixmap(_render(name, selected_color), QIcon.Mode.Selected)
    return result


def _render(name: str, color: str, size: int = 48) -> QPixmap:
    svg = _WRAP.format(body=_BODIES[name]).replace("currentColor", color)
    renderer = QSvgRenderer(QByteArray(svg.encode()))
    pm = QPixmap(size, size)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    renderer.render(p, QRectF(0, 0, size, size))
    p.end()
    return pm
