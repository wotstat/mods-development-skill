# Python-моды

Читайте для любого code-мода. Актуальный вводный материал: <https://docs.wotstat.info/guide/first-steps/environment/python/index.md>.

## Стиль именования

Для нового мода без заданных пользователем соглашений рекомендуйте стиль клиентского Python-кода:

| Элемент | Стиль | Пример |
|---|---|---|
| Классы | `PascalCase` | `VehicleStateTracker` |
| Функции, методы, параметры, переменные и свойства | `camelCase` | `getVehicleState`, `vehicleState` |
| Внутренние методы и поля | `_camelCase` или `__camelCase` по смыслу доступа | `_updateState`, `__vehicleState` |
| Константы | `UPPER_SNAKE_CASE` | `UPDATE_INTERVAL` |
| Модули и пакеты | `snake_case` | `vehicle_state.py`, `author_mod_name` |

В существующем моде сначала изучите его соглашения и окружающий код. Сохраняйте этот стиль при добавлении и изменении кода, в том числе если мод использует `snake_case` для функций и переменных. Соглашения мода имеют приоритет над рекомендацией для новых проектов.

Имена переопределяемых игровых методов, callbacks и других внешних контрактов сохраняйте точно по API; специальные методы Python вроде `__init__` также сохраняют свои имена.

## Runtime и язык

Клиент и build path используют Python 2.7. Проверяйте фактический interpreter, а не имя команды `python`. Runtime-код должен парситься Python 2.7:

- без f-strings, type annotations, dataclasses, `pathlib` и другой Python 3-only syntax/API;
- с encoding declaration в первой или второй строке, если source содержит non-ASCII literals;
- с осознанными границами `str`/`unicode`;
- с type comments или внешними stubs только если инструменты проекта их понимают.

Не считайте успешный Python 3 lint доказательством Python 2 совместимости. Компилируйте тем же Python 2.7, который использует pipeline.

Python 2 `py_compile`/`compileall` обычно записывает `.pyc` рядом с исходником. Никогда не направляйте такую компиляцию на author-owned `res/scripts/...`: компилируйте предварительно скопированное staging tree либо передавайте явный `cfile` внутри staging. Не используйте последующее удаление `.pyc` как замену изоляции; source tree должен оставаться неизменным и после успешной, и после упавшей сборки.

## Source roots и entry

Обычно полезны:

```text
wot-src/sources/res/scripts/client
wot-src/sources/res/scripts/common
wot-src/sources/res/scripts/client_common
wot-src/stubs
```

Документация описывает auto-load файлов `res/scripts/client/gui/mods/mod_*.py`, но перед созданием entry подтвердите loader и lifecycle в доступных исходниках. Если source относится к другому патчу, сообщите это и перепроверьте контракт через runtime. Не предполагайте, что loader вызывает `init()` одинаково в двух продуктах.

Держите entry тонким. Namespaced package рядом с ним снижает конфликты файлов между модами. Уникальные mod id, Python package, log prefix, settings linkage и event names должны согласовываться.

## VS Code и Pylance

Для greenfield-проекта подключите к Pylance собственный source root и все корни целевого snapshot. Типовой список выглядит так:

```json
{
  "python.analysis.extraPaths": [
    "${workspaceFolder}/res/scripts/client",
    "${workspaceFolder}/wot-src/sources/res/scripts/client",
    "${workspaceFolder}/wot-src/sources/res/scripts/common",
    "${workspaceFolder}/wot-src/sources/res/scripts/client_common",
    "${workspaceFolder}/wot-src/stubs"
  ],
  "python.autoComplete.extraPaths": [
    "${workspaceFolder}/res/scripts/client",
    "${workspaceFolder}/wot-src/sources/res/scripts/client",
    "${workspaceFolder}/wot-src/sources/res/scripts/common",
    "${workspaceFolder}/wot-src/sources/res/scripts/client_common",
    "${workspaceFolder}/wot-src/stubs"
  ],
  "python.analysis.indexing": true,
  "python.analysis.autoImportCompletions": true,
  "python.analysis.userFileIndexingLimit": 20000
}
```

`python.analysis.extraPaths` — основной search path Pylance; зеркальный `python.autoComplete.extraPaths` сохраняет ожидаемое поведение Python extension и соответствует текущей инструкции WotStat. Не копируйте пример механически: скорректируйте пути и `userFileIndexingLimit` по `counts.sources` в `.publication.json`. Значение `-1` индексирует все пользовательские файлы, но может заметно увеличить расход памяти.

Если `wot-src` лежит вне workspace, используйте переносимый `.code-workspace`, переменную проекта или локальную настройку вместо коммита абсолютного пути конкретного пользователя. Убедитесь, что каждый указанный каталог существует.

Не подключайте одновременно одноимённые модули двух продуктов в один Pylance profile: `BigWorld`, `gui` и другие imports станут неоднозначными, а diagnostics будут отражать случайный порядок путей. Для universal-мода предпочтительны отдельные MT/WoT workspace-профили. Если это невозможно, документируйте единственный активный target и порядок paths; второй продукт проверяйте отдельным переключением профиля.

После индексации откройте representative runtime-файл и проверьте как минимум:

- import собственного namespaced package;
- игровой symbol из `client`, `common` или `client_common`;
- нативный symbol из `stubs`, например `BigWorld`;
- hover, completion и переход к определению для этих трёх классов imports;
- отсутствие массовых missing-import diagnostics в Problems и ошибок Pylance в Output.

Успешная сборка мода не заменяет эту проверку: build script и Pylance используют разные search paths.

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

1. Python 2 `compileall` staged-копии или явная компиляция runtime files в staging;
2. unit-тесты чистой логики;
3. package inventory;
4. import/load marker в клиенте;
5. безопасный probe реального объекта/события;
6. пользовательский сценарий и проверка новых log errors.

## Упаковка

`.wotmod` для World of Tanks и `.mtmod` для «Мира танков» — пакеты с `meta.xml` и runtime layout. Сверяйте путь entry и ресурсов после архивации. Версия должна быть одинаковой в имени артефакта, metadata и доступной моду runtime-константе. Не включайте исходники игры и локальные stubs.

Если мод использует конфиг, сохраняйте обратную совместимость формата или выполняйте явную миграцию. Не перезаписывайте пользовательские настройки дефолтами при каждом запуске.
