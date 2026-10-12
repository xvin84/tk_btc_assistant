#!/data/data/com.termux/files/usr/bin/bash
# Установка бота в Termux. Запуск: bash termux/setup.sh
set -euo pipefail

PROJECT="$(cd "$(dirname "$0")/.." && pwd)"

# Прошлая версия скрипта ставила OpenCV, а он тянет ffmpeg, который часто
# не настраивается. Недоустановленные пакеты блокируют apt, убираем их.
leftovers="$(dpkg-query -W -f='${Package} ${Status}\n' \
    opencv opencv-python python-opencv-python ffmpeg 2>/dev/null \
    | awk '$4 != "installed" {print $1}' || true)"
if [ -n "$leftovers" ]; then
    echo "== Удаляю недоустановленные пакеты: $leftovers"
    apt-get remove -y $leftovers
    apt-get autoremove -y
fi

echo "== Обновление пакетов (если спросит про файлы настроек, жми Enter)"
pkg upgrade -y

echo "== Пакеты: Python, numpy, Pillow, adb, Termux:API"
pkg install -y python python-numpy python-pillow android-tools termux-api

echo "== Проверка"
cd "$PROJECT"
python -c "import numpy, PIL, tomllib; from btc_bot import imaging; \
print('numpy', numpy.__version__, '| Pillow', PIL.__version__, '| режим:', imaging.BACKEND)"

echo "== Ярлык для виджета Termux:Widget"
mkdir -p "$HOME/.shortcuts"
cat > "$HOME/.shortcuts/BtC-bot" <<SHORTCUT
#!/data/data/com.termux/files/usr/bin/bash
exec bash "$PROJECT/termux/btc-bot.sh"
SHORTCUT
chmod +x "$HOME/.shortcuts/BtC-bot" "$PROJECT/termux/btc-bot.sh"

cat <<'DONE'

Готово. Дальше:
  1) подключи adb телефона к самому себе (см. README, раздел «Запуск на телефоне»):
       python -m btc_bot connect
  2) открой игру на карте цепной кампании, вернись в Termux и запусти:
       bash termux/btc-bot.sh
     или кнопкой «BtC-bot» из виджета Termux:Widget.
DONE
