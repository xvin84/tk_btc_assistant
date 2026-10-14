"""English interface catalog: {Russian source string: translation}."""

CODE = "en"
NAME = "English"

CATALOG: dict[str, str] = {
    ' (пробный режим: ничего не нажимаю)':
        ' (dry run: not tapping anything)',
    '. Игра закрыта':
        '. The game was closed',
    '<p><b>1. Режим разработчика.</b> Настройки → О телефоне → 7 раз нажми «Номер сборки».</p>\n<p><b>2. Отладка по USB.</b> Настройки → Для разработчиков → «Отладка по USB».<br>\n• Xiaomi/POCO: ещё «Отладка по USB (настройки безопасности)», иначе нажатия не пройдут.<br>\n• OnePlus/realme/OPPO: если нажатия не проходят, включи «Отключить мониторинг разрешений».<br>\nТам же включи «Не выключать экран» и держи телефон на зарядке.</p>\n<p><b>3. Кабель.</b> Режим USB: «Передача файлов». На телефоне появится окно\n«Разрешить отладку по USB?». Нажми «Разрешить», лучше с галочкой «Всегда разрешать».</p>\n<p><b>4. Игра.</b> Язык игры: русский. Открой карту цепной кампании, где видна кнопка\n«Старт», и нажми «Проверить» на вкладке «Телефон».</p>\n<p><b>5. Первый запуск.</b> Включи «Пробный режим» в настройках и пройди один забег\nруками: в журнале будет видно, что бот распознаёт и куда нажал бы. Если всё верно,\nвыключи пробный режим и нажми «Запустить».</p>\n<p>Пока бот работает, телефон лучше не трогать.</p>\n<p>Без кабеля (Android 11+): «Для разработчиков» → «Беспроводная отладка», затем в\nкомандной строке <code>adb pair IP:порт</code> и <code>adb connect IP:порт</code>.</p>\n':
        '<p><b>1. Developer mode.</b> Settings → About phone → tap "Build number" 7 times.</p>\n<p><b>2. USB debugging.</b> Settings → Developer options → "USB debugging".<br>\n• Xiaomi/POCO: also "USB debugging (Security settings)", otherwise taps won\'t go through.<br>\n• OnePlus/realme/OPPO: if taps don\'t go through, enable "Disable permission monitoring".<br>\nIn the same menu enable "Stay awake" and keep the phone charging.</p>\n<p><b>3. Cable.</b> USB mode: "File transfer". The phone shows "Allow USB debugging?".\nTap "Allow", preferably with "Always allow from this computer".</p>\n<p><b>4. Game.</b> The game must be in Russian. Open the Chain Campaign map with the\n"Start" (Старт) button visible and press "Check" on the "Phone" tab.</p>\n<p><b>5. First run.</b> Enable "Dry run" in the settings and play one run by hand: the\nlog shows what the bot recognises and where it would tap. If all is right, turn dry run\noff and press "Start".</p>\n<p>Better not to touch the phone while the bot works.</p>\n<p>Without a cable (Android 11+): Developer options → "Wireless debugging", then in a\nterminal <code>adb pair IP:port</code> and <code>adb connect IP:port</code>.</p>\n',
    'ADB не отвечает: {error}':
        'ADB is not responding: {error}',
    'BtC бот остановлен: {title}':
        'BtC bot stopped: {title}',
    '[пробно] закрыл бы игру %s':
        '[dry run] would close the game %s',
    '[пробно] нажал бы %s в (%d, %d)':
        '[dry run] would tap %s at (%d, %d)',
    'adb {command} завершился с кодом {code}: {error}':
        'adb {command} exited with code {code}: {error}',
    'adb не ответил за {sec} с: {command}':
        'adb did not respond within {sec} s: {command}',
    'adb скачан: %s':
        'adb downloaded: %s',
    '{error}\n\nМожно скачать вручную: developer.android.com/tools/releases/platform-tools и распаковать папку platform-tools рядом с программой ({folder}).':
        '{error}\n\nYou can download it manually from developer.android.com/tools/releases/platform-tools and unpack the platform-tools folder next to the app ({folder}).',
    '{screen}. Открой карту цепной кампании с кнопкой «Старт»':
        '{screen}. Open the Chain Campaign map with the "Start" button',
    '{serial} в состоянии {state}: {hint}':
        '{serial} is {state}: {hint}',
    '«АВТО» не включается после {taps} нажатий':
        '"AUTO" doesn\'t turn on after {taps} taps',
    'Автобой был выключен, включаю':
        'Auto-battle was off, turning it on',
    'Бой идёт дольше {sec:.0f} с':
        'The battle has lasted more than {sec:.0f} s',
    'Бот ещё работает. Остановить его и закрыть программу?':
        'The bot is still running. Stop it and close the app?',
    'Бот запущен%s. Игра: %s':
        'Bot started%s. Game: %s',
    'Бот работает':
        'The bot is running',
    'Бот только смотрит и пишет в журнал, куда нажал бы. Играешь ты сам.':
        'The bot only watches and logs where it would tap. You play yourself.',
    'Бот упал: %s':
        'The bot crashed: %s',
    'В архиве {url} не нашлось {name}':
        '{name} was not found in the archive {url}',
    'Выбери телефон':
        'Choose the phone',
    'Глубина кампании повышена (за сессию: %d)':
        'Campaign depth increased (this session: %d)',
    'Готов к запуску':
        'Ready to start',
    'Готово':
        'Done',
    'Журнал':
        'Log',
    'Забег — один этап кампании: бои подряд до экрана «ПОБЕДА». Сколько в нём боёв, боту неважно.':
        'A run is one campaign stage: battles in a row up to the "VICTORY" screen. The bot doesn\'t care how many battles it has.',
    'Забегов: {runs}, глубина +{depth}':
        'Runs: {runs}, depth +{depth}',
    'Закончилась стамина':
        'Out of stamina',
    'Закрываю игру %s':
        'Closing the game %s',
    'Закрыть игру при поражении':
        'Close the game on defeat',
    'Игра':
        'Game',
    'Играй сам: бот только смотрит':
        'Play yourself: the bot only watches',
    'Итого: забегов %d, повышений глубины %d':
        'Total: %d runs, %d depth-ups',
    'Кадр при каждой смене экрана попадёт в папку с логами':
        'A frame of every screen change goes to the log folder',
    'Как подготовить телефон':
        'Preparing the phone',
    'Нажал «Старт» {taps} раза, но расстановка не открылась. Скорее всего, закончилась стамина':
        'Pressed "Start" {taps} times, but the team setup didn\'t open. Most likely out of stamina',
    'Нажимаю %s в (%d, %d)':
        'Tapping %s at (%d, %d)',
    'Нажимаю «СТАРТ» в расстановке, но бой не начинается':
        'Tapping "START" in the team setup, but the battle doesn\'t begin',
    'Нажми «Запустить»':
        'Press "Start"',
    'Настройки':
        'Settings',
    'Не больше':
        'At most',
    'Не готово':
        'Not ready',
    'Не знаю пакет игры, закрыть её не могу (укажи device.package)':
        "Unknown game package, can't close the game (set device.package)",
    'Не найден adb ({adb}). Установи Android platform-tools и добавь adb в PATH или укажи путь в config.toml':
        'adb not found ({adb}). Install Android platform-tools and add adb to PATH or set its path in config.toml',
    'Не понял, какой пакет у игры (на экране %s, установлены %s). Укажи --package или device.package в config.toml':
        "Couldn't tell the game package (on screen %s, installed %s). Set --package or device.package in config.toml",
    'Не удалось декодировать скриншот (пустой ответ screencap?)':
        "Couldn't decode the screenshot (empty screencap output?)",
    'Не удалось закрыть игру: %s':
        "Couldn't close the game: %s",
    'Не удалось скачать adb':
        "Couldn't download adb",
    'Не удалось скачать adb: %s':
        "Couldn't download adb: %s",
    'Не удалось сохранить кадр %s: %s':
        "Couldn't save frame %s: %s",
    'Не удалось сохранить настройки окна: %s':
        "Couldn't save window settings: %s",
    'Незнакомый экран дольше {sec:.0f} с':
        'Unfamiliar screen for more than {sec:.0f} s',
    'Незнакомый экран после боя дольше {sec:.0f} с: похоже на поражение':
        'Unfamiliar screen after a battle for more than {sec:.0f} s: looks like a defeat',
    'Нет картинки':
        'No picture',
    'Нет связи с телефоном':
        'No connection to the phone',
    'Нужен adb':
        'adb is needed',
    'О программе':
        'About',
    'Останавливаю…':
        'Stopping…',
    'Остановка (%s): %s':
        'Stopped (%s): %s',
    'Остановлено':
        'Stopped',
    'Остановлено пользователем':
        'Stopped by the user',
    'Открой в игре карту цепной кампании, где видна кнопка «Старт», и нажми «Проверить». Как подготовить телефон, написано в «Справке».':
        'Open the Chain Campaign map in the game with the "Start" button visible and press "Check". How to prepare the phone is described under "Help".',
    'Открой карту цепной кампании':
        'Open the Chain Campaign map',
    'Открыть папку с логами':
        'Open log folder',
    'Официальный набор Android platform-tools с сайта Google, около 7 МБ':
        'The official Android platform-tools from Google, about 7 MB',
    'Ошибка':
        'Error',
    'Ошибка: %s':
        'Error: %s',
    'Папка с логами':
        'Log folder',
    'Перед началом':
        'Before you start',
    'Победа! Пройдено забегов: %d':
        'Victory! Runs done: %d',
    'Поведение':
        'Behaviour',
    'Подключение':
        'Connection',
    'Подключено несколько устройств':
        'Several devices connected',
    'Подключено несколько устройств ({serials}): укажи нужное через --serial':
        'Several devices connected ({serials}): pick one with --serial',
    'Подключено несколько устройств: выбери нужное':
        'Several devices connected: choose one',
    'Подключи телефон и нажми «Проверить»':
        'Connect the phone and press "Check"',
    'Подсказка на вкладке «Телефон»':
        'See the hint on the "Phone" tab',
    'Пока есть стамина':
        'While stamina lasts',
    'Помощник Break the Chains':
        'Break the Chains Assistant',
    'Помощник · v{version}':
        'Assistant · v{version}',
    'Поражение':
        'Defeat',
    'После «Старт» не открылась расстановка. Скорее всего, закончилась стамина':
        'The team setup didn\'t open after "Start". Most likely out of stamina',
    'После текущего шага':
        'After the current step',
    'Пробный режим':
        'Dry run',
    'Пробный режим (ничего не нажимать)':
        "Dry run (don't tap anything)",
    'Проверить':
        'Check',
    'Проверь кабель и нажми «Проверить»':
        'Check the cable and press "Check"',
    'Проверяю телефон…':
        'Checking the phone…',
    'Проверяю…':
        'Checking…',
    'Пройдено забегов: {runs}, лимит достигнут':
        'Runs done: {runs}, limit reached',
    'Работает':
        'Running',
    'Распознано: {screen}':
        'Recognised: {screen}',
    'Распознано: —':
        'Recognised: —',
    'Сбой ADB (%d/%d): %s':
        'ADB failure (%d/%d): %s',
    'Связываюсь через adb':
        'Connecting through adb',
    'Скачать adb':
        'Download adb',
    'Скачиваю…':
        'Downloading…',
    'Скачиваю… {kb} КБ':
        'Downloading… {kb} KB',
    'Скачиваю… {percent}%':
        'Downloading… {percent}%',
    'Сколько забегов':
        'How many runs',
    'Скриншот в режиме %s не разобрался (%s), перехожу на PNG':
        "Couldn't decode a %s screenshot (%s), switching to PNG",
    'Сохранять кадры (для отчёта об ошибке)':
        'Save frames (for a bug report)',
    'Справка':
        'Help',
    'Страница на GitHub':
        'GitHub page',
    'Телефон':
        'Phone',
    'Телефон лучше не трогать':
        'Better not to touch the phone',
    'Телефон не виден в `adb devices`. Включи «Отладку по USB» и подключи кабель (режим USB «Передача файлов»)':
        'The phone isn\'t listed in `adb devices`. Enable "USB debugging" and connect the cable (USB mode "File transfer")',
    'Телефон не готов':
        'The phone is not ready',
    'Телефон подключён':
        'Phone connected',
    'Устройство {serial} не найдено в `adb devices`':
        'Device {serial} not found in `adb devices`',
    'Через него программа видит экран и нажимает':
        'The app uses it to see the screen and tap',
    'Экран {screen} не меняется {sec:.0f} с':
        "Screen {screen} hasn't changed for {sec:.0f} s",
    'Экран итогов без «ПОБЕДА»: похоже на поражение':
        'Results screen without "VICTORY": looks like a defeat',
    'Экран: %s':
        'Screen: %s',
    'Экран: %s (был %s)':
        'Screen: %s (was %s)',
    'Это неофициальная программа. Она нажимает на экран вместо тебя, а автоматизация нарушает правила большинства игр.\n\nБот не лезет в клиент игры и не трогает трафик, но риск блокировки аккаунта не нулевой. Пользуясь программой, ты принимаешь этот риск.':
        "This is an unofficial app. It taps the screen for you, and automation breaks the rules of most games.\n\nThe bot doesn't touch the game client or its traffic, but the risk of an account ban is not zero. By using the app you accept this risk.",
    'бой':
        'battle',
    'время работы':
        'running time',
    'готово':
        'done',
    'забегов пройдено':
        'runs done',
    'загрузка':
        'loading',
    'итоги боя':
        'battle results',
    'итоги: победа':
        'results: victory',
    'карта кампании':
        'campaign map',
    'карта кампании, «Получить все»':
        'campaign map, "Claim all"',
    'карта кампании, есть «Старт»':
        'campaign map, "Start" is visible',
    'кончилась стамина':
        'out of stamina',
    'не найден. Скачай его кнопкой ниже: это официальный набор Android platform-tools':
        "not found. Download it with the button below: it's the official Android platform-tools",
    'не определена':
        'unknown',
    'не распознан':
        'not recognised',
    'нет прав на USB-устройство (no permissions). Нужны udev-правила: в Arch пакет android-udev. После установки переподключи кабель.':
        'no permission for the USB device (no permissions). udev rules are needed: the android-udev package on Arch. Reconnect the cable after installing it.',
    'ошибка':
        'error',
    'победа в бою':
        'battle won',
    'повышение глубины':
        'depth up',
    'повышений глубины':
        'depth-ups',
    'подключено несколько устройств, выбери нужное':
        'several devices connected, choose one',
    'полученные награды':
        'rewards received',
    'поражение':
        'defeat',
    'проверь подключение и `adb devices`.':
        'check the connection and `adb devices`.',
    'расстановка':
        'team setup',
    'связь потеряна: {error}':
        'connection lost: {error}',
    'телефон offline. Переподключи кабель или выполни `adb kill-server`.':
        'the phone is offline. Reconnect the cable or run `adb kill-server`.',
    'телефон не разрешил отладку этому компьютеру. Разблокируй экран и нажми «Разрешить» в окне «Разрешить отладку по USB?» (лучше с галочкой «Всегда разрешать с этого компьютера»). Если окна нет: «Для разработчиков» → «Отозвать авторизацию отладки по USB», затем `adb kill-server` и переподключи кабель.':
        'the phone hasn\'t allowed debugging for this computer. Unlock the screen and tap "Allow" in the "Allow USB debugging?" window (preferably with "Always allow from this computer"). If there is no window: Developer options → "Revoke USB debugging authorisations", then `adb kill-server` and reconnect the cable.',
    'уровень пройден':
        'level cleared',
    'цепная реакция':
        'chain reaction',
    '■  Остановить':
        '■  Stop',
    '▶  Запустить':
        '▶  Start',
}
