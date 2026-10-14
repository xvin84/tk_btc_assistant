# Сборка программы с окном: uv run pyinstaller packaging/btc-bot.spec --noconfirm
# Результат: dist/BtcAssistant/ (программа и папка _internal рядом с ней),
# на macOS ещё dist/BtcAssistant.app.
import sys
import tomllib
from pathlib import Path

ROOT = Path(SPECPATH).parent
VERSION = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]["version"]

a = Analysis(
    [str(ROOT / "packaging" / "launcher.py")],
    pathex=[str(ROOT)],
    datas=[(str(ROOT / "templates"), "templates")],
    # Собранная программа распознаёт экраны через numpy + Pillow: OpenCV с его
    # ffmpeg весит 60–150 МБ, а кадр через numpy считается ~80 мс против ~30 мс,
    # что теряется на фоне ~900 мс на сам снимок экрана. Tk окну не нужен.
    excludes=["pytest", "cv2", "tkinter"],
)
# OpenGL окну не нужен, а из переводов Qt хватает русского для кнопок диалогов
a.binaries = [b for b in a.binaries if "opengl32sw" not in b[0]]
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

if sys.platform == "darwin":
    app = BUNDLE(
        coll,
        name="BtcAssistant.app",
        bundle_identifier="io.github.xvin84.btcassistant",
        info_plist={"NSHighResolutionCapable": True, "CFBundleShortVersionString": VERSION},
    )
