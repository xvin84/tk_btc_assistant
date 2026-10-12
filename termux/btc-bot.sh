#!/data/data/com.termux/files/usr/bin/bash
# Запуск бота прямо на телефоне. Аргументы передаются в `run`, например:
#   bash termux/btc-bot.sh --max-runs 10
set -uo pipefail

cd "$(dirname "$0")/.."

# Не даём Android усыпить Termux, пока бот работает
if command -v termux-wake-lock >/dev/null; then
    termux-wake-lock
    trap 'termux-wake-unlock' EXIT
fi

# Вывод connect показываем как есть (там может быть просьба нажать «Разрешить»)
SERIAL="$(python -u -m btc_bot connect | tee /dev/stderr | sed -n 's/^Подключено: //p')"
if [ -z "$SERIAL" ]; then
    echo "Не удалось подключиться к adb телефона (подробности выше)."
    read -rp "Нажми Enter, чтобы закрыть..." _
    exit 1
fi

python -m btc_bot --serial "$SERIAL" --capture raw run --launch "$@"
code=$?
echo
echo "Бот остановился (код $code). Лог: logs/"
read -rp "Нажми Enter, чтобы закрыть..." _
exit $code
