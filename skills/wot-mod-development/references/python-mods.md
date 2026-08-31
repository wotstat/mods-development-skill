# Python-моды

Читайте для любого code-мода. Актуальный вводный материал: <https://docs.wotstat.info/guide/first-steps/environment/python/>.

## Runtime и язык

Клиент и build path используют Python 2.7. Проверяйте фактический interpreter, а не имя команды `python`. Runtime-код должен парситься Python 2.7:

- без f-strings, type annotations, dataclasses, `pathlib` и другой Python 3-only syntax/API;
- с encoding declaration в первой или второй строке, если source содержит non-ASCII literals;
- с осознанными границами `str`/`unicode`;
- с type comments или внешними stubs только если инструменты проекта их понимают.

Не считайте успешный Python 3 lint доказательством Python 2 совместимости. Компилируйте тем же Python 2.7, который использует pipeline.

## Source roots и entry

Обычно полезны:

```text
wot-src/sources/res/scripts/client
wot-src/sources/res/scripts/common
wot-src/sources/res/scripts/client_common
```

Документация описывает auto-load файлов `res/scripts/client/gui/mods/mod_*.py`, но перед созданием entry подтвердите loader и lifecycle в доступных исходниках. Если source относится к другому патчу, сообщите это и перепроверьте контракт через runtime. Не предполагайте, что loader вызывает `init()` одинаково в двух продуктах.

Держите entry тонким. Namespaced package рядом с ним снижает конфликты файлов между модами. Уникальные mod id, Python package, log prefix, settings linkage и event names должны согласовываться.

## Работа с игровым API

Порядок поиска:

1. определение нужного поведения в game source;
2. существующий игровой caller/consumer;
3. доступное event или service interface;
4. только затем narrow monkey patch.

При patching сохраняйте ссылку на оригинал, вызывайте его в доказанном порядке, возвращайте его значение и принимайте совместимую форму аргументов. Установка должна быть идемпотентной. Не ловите все исключения вокруг целого feature; логируйте точную стадию и не оставляйте наполовину установленный patch.

Dependency injection, app loader, Wulf/Scaleform factories и другие framework-механизмы меняются. Импорт и сигнатуру всегда берите из целевой версии исходников.

## Чистая логика и тесты

Отделяйте вычисления/преобразования от BigWorld/gui объектов только когда это даёт реальный тестовый seam. Pure logic можно сделать dual-compatible с Python 2/3 и тестировать вне клиента. Game adapters проверяйте source inspection и runtime smoke tests; огромные mocks клиента обычно создают ложную уверенность.

Полезная лестница:

1. Python 2 `compileall` или явная компиляция runtime files;
2. unit-тесты чистой логики;
3. package inventory;
4. import/load marker в клиенте;
5. безопасный probe реального объекта/события;
6. пользовательский сценарий и проверка новых log errors.

## Упаковка

`.wotmod` для World of Tanks и `.mtmod` для «Мира танков» — пакеты с `meta.xml` и runtime layout. Сверяйте путь entry и ресурсов после архивации. Версия должна быть одинаковой в имени артефакта, metadata и доступной моду runtime-константе. Не включайте исходники игры и локальные stubs.

Если мод использует конфиг, сохраняйте обратную совместимость формата или выполняйте явную миграцию. Не перезаписывайте пользовательские настройки дефолтами при каждом запуске.
