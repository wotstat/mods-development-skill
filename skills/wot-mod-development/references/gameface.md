# Gameface и Unbound/Wulf UI

Читайте для HTML/CSS/JavaScript, `res_map`, Coherent Gameface, GF view, Unbound или нового Wulf UI. Теория: <https://docs.wotstat.info/guide/scripting/gameface-theory/index.md>. DevTools: <https://docs.wotstat.info/guide/first-steps/devtools/index.md>.

## Сначала классификация

Окна Wulf могут быть реализованы через Gameface, Unbound или Scaleform. HTML в ресурсах ещё не доказывает, что нужный экран — GF. В snapshot `wotstat/wot-src` ищите игровые layouts/assets в `sources-gameface/`, Python view/window — в `sources/`, а нативные контракты — в `stubs/`; затем найдите конкретный resource id и игровой аналог.

Gameface похож на браузер, но им не является: версия engine и Web APIs ограничена клиентом. Не выбирайте framework, syntax target или browser API только потому, что это работает в современном Chrome.

## Зависимости и ресурсы

WotStat описывает `OpenWG.Gameface`/`net.openwg.gameface` для регистрации mod resources через `res_map`. WG и Lesta могут требовать разные варианты зависимости. Перед изменением установки игры проверьте актуальные upstream/release instructions и получите нужное разрешение пользователя.

Для custom layout обычно нужны:

- уникальный namespaced `itemID` в `mods/configs/res_map/*.json`;
- точный `coui://` path и entrance;
- Python accessor/view/window по API целевого source commit;
- HTML/CSS/JS в runtime layout, ожидаемом target client;
- установленная совместимая resource-registration dependency.

Не редактируйте основной игровой `res_map.json` вручную, если проект использует mod registration layer. Не копируйте `ModDynAccessor`, `ViewSettings`, flags или model contract без проверки source/dependency версии.

Node/npm/bundler не обязательны для каждого GF-мода. Для небольшого greenfield UI начинайте с минимального toolchain; добавляйте TypeScript/framework/bundler только при реальной пользе. Если проект уже использует frontend stack, сохраняйте его lockfile и conventions.

Опциональные type packages вроде `wot-gameface-types` помогают редактору, но не являются runtime-доказательством. Сверяйте их версию с клиентом и проверяйте нативное поведение.

## Model и lifecycle

Проверьте по исходникам и runtime:

- когда доступен engine и нужна ли `engine.whenReady`;
- property/command indices и аргументы model commands;
- какие nested models требуют отдельной подписки;
- когда page/view уничтожается при навигации;
- как отписывать JS/Python callbacks и не дублировать listeners;
- какой app/scope создаёт окно в ангаре или бою.

JS → Python commands валидируйте как недоверенный boundary: проверяйте форму и допустимые значения аргументов. Не выполняйте произвольный код/пути, полученные из UI.

Для логов учитывайте фактическую интеграцию: документация отмечает, что `console.warn` виден в game logs там, где обычный `console.log` может не отображаться.

## DevTools

Chrome DevTools через `wotstat-chrome-devtools-protocol` полезен для DOM/CSS/JS inspection. Он не сохраняет изменения и не генерирует мод. Используйте его как наблюдение:

1. выберите реальную вкладку/страницу, присутствующую на экране;
2. зафиксируйте DOM/resource id и runtime error;
3. перенесите подтверждённое изменение в source проекта;
4. пересоберите и повторно проверьте клиент.

Не включайте remote debugging наружу без необходимости. Не публикуйте MCP/DevTools tokens и локальные адреса с секретами.

## Визуальная проверка

В обычной итерации проверьте изменённый экран/сценарий и новые ошибки. UI scale, несколько разрешений/aspect ratios и длинные строки проверяйте при изменении layout; повторную навигацию, focus и создание page — при изменении соответствующего поведения. Полную применимую матрицу используйте для готовности релиза. Проверяйте затронутые продукты; совместимость universal-мода заявляйте только после отдельной проверки обоих: одинаковый HTML не гарантирует одинаковый Wulf/model contract.
