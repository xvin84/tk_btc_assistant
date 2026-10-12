#!/data/data/com.termux/files/usr/bin/bash
# Установка бота в Termux. Запуск: bash termux/setup.sh
set -euo pipefail

PROJECT="$(cd "$(dirname "$0")/.." && pwd)"

echo "== Пакеты (OpenCV лежит в x11-repo, он большой: несколько сотен МБ)"
pkg update -y
pkg install -y x11-repo
pkg install -y python python-numpy opencv-python android-tools termux-api

echo "== Проверка Python-модулей"
python -c "import cv2, numpy, tomllib; print('OpenCV', cv2.__version__, '| numpy', numpy.__version__)"

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
