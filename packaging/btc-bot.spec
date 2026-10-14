# Сборка программы с окном: uv run pyinstaller packaging/btc-bot.spec --noconfirm
# Результат: dist/BtcAssistant/ (exe и папка _internal рядом с ним).
from pathlib import Path

ROOT = Path(SPECPATH).parent

a = Analysis(
    [str(ROOT / "packaging" / "launcher.py")],
    pathex=[str(ROOT)],
    datas=[(str(ROOT / "templates"), "templates")],
    # Pillow нужен только без OpenCV (Termux), Tk окну больше не нужен
    excludes=["pytest", "PIL", "tkinter"],
)
# Видео не читаем: ffmpeg из OpenCV (~25 МБ на Windows) не нужен. OpenGL окну тоже
# не нужен, а из переводов Qt хватает русского для кнопок диалогов.
a.binaries = [b for b in a.binaries
              if "opencv_videoio_ffmpeg" not in b[0] and "opengl32sw" not in b[0]]
a.datas = [d for d in a.datas
           if "translations" not in d[0].replace("\\", "/").split("/")
           or Path(d[0]).name.startswith("qtbase_ru")]
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
