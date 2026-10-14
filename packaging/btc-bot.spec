# Сборка программы с окном: uv run pyinstaller packaging/btc-bot.spec --noconfirm
# Результат: dist/BtcAssistant/ (exe и папка _internal рядом с ним).
from pathlib import Path

ROOT = Path(SPECPATH).parent

a = Analysis(
    [str(ROOT / "packaging" / "launcher.py")],
    pathex=[str(ROOT)],
    datas=[(str(ROOT / "templates"), "templates")],
    excludes=["pytest", "PIL"],  # Pillow нужен только без OpenCV (Termux)
)
# Видео не читаем: ffmpeg из OpenCV (~25 МБ на Windows) не нужен
a.binaries = [b for b in a.binaries if "opencv_videoio_ffmpeg" not in b[0]]
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="BtcAssistant",
    console=False,
)
coll = COLLECT(exe, a.binaries, a.datas, name="BtcAssistant")
