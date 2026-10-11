import sys

try:
    from .cli import main
except ModuleNotFoundError as e:
    if e.name not in ("cv2", "numpy"):
        raise
    sys.exit(
        f"Не установлен модуль {e.name}. Поставь зависимости и запускай через uv:\n"
        "  uv sync\n"
        "  uv run btc-bot doctor"
    )

sys.exit(main())
