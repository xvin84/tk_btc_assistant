"""Командная строка: python -m btc_bot <команда>."""

from __future__ import annotations

import argparse
import logging
import sys
import time
from datetime import datetime
from pathlib import Path

from .adb import LOCAL_HOST, LOCAL_TCP_PORT, AdbError, Device, connect_local
from .campaign import CampaignBot
from .config import Config, load_config
from .notify import notify
from .screens import Classifier
from .vision import (
    PROJECT_ROOT,
    TemplateLibrary,
    crop_template,
    load_image,
    normalize,
    rebuild_templates,
    save_image,
)

log = logging.getLogger("btc_bot")

GAME_HINTS = ("funcat", "tgbtc")


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        # Консоль Windows по умолчанию не в UTF-8
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")

    parser = build_parser()
    args = parser.parse_args(argv)
    if not getattr(args, "command", None):
        parser.print_help()
        return 1
    try:
        return args.func(args)
    except AdbError as e:
        log.error("Ошибка ADB: %s", e)
        return 1
    except KeyboardInterrupt:
        log.info("Остановлено пользователем")
        return 130


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="btc-bot",
                                description="Помощник для Tokyo Ghoul: Break the Chains")
    p.add_argument("--config", default=str(PROJECT_ROOT / "config.toml"),
                   help="файл настроек (по умолчанию config.toml в корне проекта)")
    p.add_argument("--serial", help="серийный номер устройства из `adb devices` "
                                    "(или адрес вида 127.0.0.1:5555)")
    p.add_argument("--capture", choices=("png", "raw"),
                   help="как снимать экран: png (по кабелю) или raw (на самом телефоне)")
    p.add_argument("-v", "--verbose", action="store_true", help="подробный лог")
    sub = p.add_subparsers(dest="command")

    r = sub.add_parser("run", help="автопрохождение цепной кампании")
    r.add_argument("--dry-run", action="store_true",
                   help="только распознавать и писать в лог, ничего не нажимать")
    r.add_argument("--max-runs", type=int, help="сколько забегов пройти (0 = без лимита)")
    r.add_argument("--package", help="пакет игры (по умолчанию — открытое приложение)")
    r.add_argument("--save-frames", action="store_true",
                   help="сохранять кадр при каждой смене экрана")
    r.add_argument("--no-exit-game", action="store_true",
                   help="не закрывать игру при поражении")
    r.add_argument("--launch", action="store_true",
                   help="сначала вывести игру на передний план (запуск с самого телефона)")
    r.set_defaults(func=cmd_run)

    con = sub.add_parser("connect", help="подключить adb телефона к самому себе (Termux)")
    con.add_argument("--port", type=int,
                     help="порт с главного экрана «Беспроводной отладки» "
                          "(если не указан, ищется сам)")
    con.add_argument("--tcp-port", type=int, default=LOCAL_TCP_PORT,
                     help="постоянный порт adb (по умолчанию %(default)s)")
    con.set_defaults(func=cmd_connect)

    pa = sub.add_parser("pair", help="сопряжение с «Беспроводной отладкой» (один раз)")
    pa.add_argument("port", type=int, help="порт из окна «Подключение с помощью кода»")
    pa.add_argument("code", help="шестизначный код из того же окна")
    pa.add_argument("--host", default=LOCAL_HOST)
    pa.set_defaults(func=cmd_pair)

    rec = sub.add_parser("record", help="записывать скриншоты по касаниям и/или по таймеру")
    rec.add_argument("--interval", type=float, help="ещё и скриншот каждые N секунд")
    rec.add_argument("--no-taps", action="store_true", help="не следить за касаниями")
    rec.add_argument("--duration", type=float, help="остановиться через N секунд")
    rec.add_argument("--rotation", type=int, choices=(0, 1, 2, 3),
                     help="поворот экрана, если касания отмечаются не там")
    rec.add_argument("--out", help="папка (по умолчанию recordings/<дата>)")
    rec.set_defaults(func=cmd_record)

    snap = sub.add_parser("snap", help="сохранить текущий экран и показать, как он распознан")
    snap.add_argument("name", nargs="?", help="имя файла (без расширения)")
    snap.add_argument("--out", default=str(PROJECT_ROOT / "samples" / "device"))
    snap.set_defaults(func=cmd_snap)

    d = sub.add_parser("doctor", help="проверить ADB, телефон и распознавание")
    d.set_defaults(func=cmd_doctor)

    c = sub.add_parser("classify", help="распознать экраны на готовых скриншотах")
    c.add_argument("images", nargs="+")
    c.add_argument("--scores", action="store_true", help="показать оценки всех шаблонов")
    c.set_defaults(func=cmd_classify)

    cr = sub.add_parser("crop", help="вырезать новый шаблон из скриншота")
    cr.add_argument("image")
    cr.add_argument("box", nargs=4, type=int, metavar=("X1", "Y1", "X2", "Y2"),
                    help="рамка в рабочих координатах (кадр шириной 1280)")
    cr.add_argument("--name", required=True)
    cr.add_argument("--threshold", type=float)
    cr.add_argument("--note")
    cr.set_defaults(func=cmd_crop)

    rb = sub.add_parser("rebuild-templates",
                        help="перевырезать все шаблоны из исходных скриншотов")
    rb.set_defaults(func=cmd_rebuild)
    return p


# --- общие помощники ----------------------------------------------------

def setup_logging(verbose: bool, log_file: Path | None = None) -> None:
    root = logging.getLogger("btc_bot")
    root.setLevel(logging.DEBUG if verbose else logging.INFO)
    root.handlers.clear()
    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(logging.Formatter("%(asctime)s %(message)s", "%H:%M:%S"))
    root.addHandler(console)
    if log_file:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        fh = logging.FileHandler(log_file, encoding="utf-8")
        fh.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
        root.addHandler(fh)


def session_dir(base: str | Path) -> Path:
    base = Path(base)
    if not base.is_absolute():
        base = PROJECT_ROOT / base
    return base / datetime.now().strftime("%Y-%m-%d_%H-%M-%S")


def make_device(args, cfg: Config, check: bool = True) -> Device:
    device = Device(serial=args.serial or cfg.device.serial or None, adb=cfg.device.adb,
                    capture=args.capture or cfg.device.capture)
    if check:
        device.ensure_ready()
    return device


def resolve_package(device: Device, configured: str | None) -> str | None:
    if configured:
        return configured
    current = device.current_package()
    if current and any(h in current for h in GAME_HINTS):
        return current
    installed = device.packages("funcat")
    if len(installed) == 1:
        return installed[0]
    log.warning("Не понял, какой пакет у игры (на экране %s, установлены %s). "
                "Укажи --package или device.package в config.toml", current, installed)
    return None


def warn_if_screen_may_sleep(device: Device) -> None:
    try:
        value = device.stay_on_setting()
    except AdbError:
        return
    if value == 0:
        log.warning("Экран может погаснуть посреди забега: поставь телефон на зарядку и "
                    "включи «Для разработчиков» → «Не выключать экран»")


# --- команды ------------------------------------------------------------

def cmd_run(args) -> int:
    cfg = load_config(args.config)
    if args.max_runs is not None:
        cfg.campaign.max_runs = args.max_runs
    if args.save_frames:
        cfg.campaign.save_frames = True
    if args.no_exit_game:
        cfg.campaign.exit_game_on_defeat = False
        cfg.campaign.exit_game_on_error = False

    out = session_dir(cfg.logs_dir)
    setup_logging(args.verbose, out / "bot.log")
    device = make_device(args, cfg)
    package = resolve_package(device, args.package or cfg.device.package)
    warn_if_screen_may_sleep(device)
    if args.launch:
        if not package:
            raise AdbError("Не знаю, какую игру открыть: укажи --package")
        log.info("Вывожу игру на передний план")
        device.launch(package)
        time.sleep(3)
    classifier = Classifier(TemplateLibrary.load())
    bot = CampaignBot(device, classifier, cfg.campaign, package=package, session_dir=out,
                      dry_run=args.dry_run)
    result = bot.run()
    log.info("Лог и кадры: %s", out)
    notify(f"BtC бот остановлен: {STOP_TITLES.get(result.kind, result.kind)}",
           f"{result.reason}. Забегов: {result.runs_done}, глубина +{result.depth_ups}")
    return result.exit_code


STOP_TITLES = {
    "done": "готово",
    "no_stamina": "кончилась стамина",
    "defeat": "поражение",
    "error": "ошибка",
}


def cmd_connect(args) -> int:
    cfg = load_config(args.config)
    setup_logging(args.verbose)
    serial = connect_local(adb=cfg.device.adb, wireless_port=args.port, tcp_port=args.tcp_port)
    print(f"Подключено: {serial}")
    print(f"Запуск: python -m btc_bot --serial {serial} --capture raw run --launch")
    return 0


def cmd_pair(args) -> int:
    cfg = load_config(args.config)
    setup_logging(args.verbose)
    out = Device(adb=cfg.device.adb).pair(f"{args.host}:{args.port}", args.code)
    print(out or "Сопряжение выполнено")
    return 0


def cmd_record(args) -> int:
    from .recorder import Recorder

    cfg = load_config(args.config)
    out = Path(args.out) if args.out else session_dir("recordings")
    setup_logging(args.verbose, out / "record.log")
    device = make_device(args, cfg)
    rec = Recorder(device, out, interval=args.interval, taps=not args.no_taps,
                   rotation=args.rotation)
    rec.run(duration=args.duration)
    return 0


def cmd_snap(args) -> int:
    cfg = load_config(args.config)
    setup_logging(args.verbose)
    device = make_device(args, cfg)
    frame = device.screenshot()
    name = args.name or datetime.now().strftime("snap_%Y-%m-%d_%H-%M-%S")
    path = Path(args.out) / f"{name}.png"
    save_image(path, frame)
    classifier = Classifier(TemplateLibrary.load())
    det = classifier.classify(normalize(frame)[0])
    print(f"Сохранено: {path} ({frame.shape[1]}x{frame.shape[0]})")
    print(f"Экран: {det.screen}")
    return 0


def cmd_classify(args) -> int:
    setup_logging(args.verbose)
    classifier = Classifier(TemplateLibrary.load())
    for image in args.images:
        frame, _ = normalize(load_image(image))
        det = classifier.classify(frame)
        line = f"{image}: {det.screen}"
        if det.screen == "battle":
            auto, _ = classifier.auto_state(frame)
            line += f" (АВТО: {'вкл' if auto else 'выкл' if auto is False else '?'})"
        print(line)
        if args.scores:
            for name, score in classifier.scores(frame).items():
                print(f"    {name:24} {score:.2f}")
    return 0


def cmd_crop(args) -> int:
    setup_logging(args.verbose)
    out = crop_template(args.image, tuple(args.box), args.name, threshold=args.threshold,
                        note=args.note)
    print(f"Шаблон сохранён: {out}")
    return 0


def cmd_rebuild(args) -> int:
    setup_logging(args.verbose)
    names = rebuild_templates()
    print(f"Перевырезано шаблонов: {len(names)}")
    return 0


def cmd_doctor(args) -> int:
    cfg = load_config(args.config)
    setup_logging(args.verbose)
    device = make_device(args, cfg, check=False)
    ok = True

    def check(title, fn):
        nonlocal ok
        try:
            value = fn()
            shown = "получен" if hasattr(value, "shape") else value
            print(f"[ok] {title}: {shown}")
            return value
        except Exception as e:  # noqa: BLE001 — диагностика должна дойти до конца
            ok = False
            print(f"[!!] {title}: {e}")
            return None

    check("Устройства adb", device.devices)
    try:
        device.ensure_ready()
    except AdbError as e:
        print(f"[!!] Телефон не готов: {e}")
        return 1
    check("Размер экрана", device.wm_size)
    check("Поворот (0..3)", device.rotation)
    check("Приложение на экране", device.current_package)
    stay_on = check("«Не выключать экран» (0 = выкл.)", device.stay_on_setting)
    if stay_on == 0:
        print("     Для долгой работы включи «Для разработчиков» → «Не выключать экран» "
              "и держи телефон на зарядке")
    check("Установленные пакеты funcat", lambda: device.packages("funcat"))

    started = time.monotonic()
    frame = check("Скриншот", device.screenshot)
    if frame is not None:
        print(f"     {frame.shape[1]}x{frame.shape[0]} за {time.monotonic() - started:.2f} с")
        lib = TemplateLibrary.load()
        classifier = Classifier(lib)
        check("Шаблонов загружено", lambda: len(lib.templates))
        check("Текущий экран", lambda: classifier.classify(normalize(frame)[0]).screen)
    check("Сенсор для записи", device.touch_axes)
    return 0 if ok else 1
