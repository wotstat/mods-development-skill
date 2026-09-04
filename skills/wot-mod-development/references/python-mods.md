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

В обоих продуктах loader автоматически загружает `res/scripts/client/gui/mods/mod_*.py` и вызывает `init()`. Используйте этот известный контракт без повторного исследования загрузчика; обращайтесь к его исходникам при конкретном сбое загрузки.

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

При первичной настройке IDE или изменении её paths/interpreter после индексации откройте representative runtime-файл и проверьте как минимум (не повторяйте после обычных правок мода):

- import собственного namespaced package;
- игровой symbol из `client`, `common` или `client_common`;
- нативный symbol из `stubs`, например `BigWorld`;
- hover, completion и переход к определению для этих трёх классов imports;
- отсутствие массовых missing-import diagnostics в Problems и ошибок Pylance в Output.

Успешная сборка мода не заменяет эту проверку: build script и Pylance используют разные search paths.

## Работа с игровым API

Используйте [правила исследования API](evidence-and-intake.md#исследование-api) и требования к hooks из [рабочего цикла](../SKILL.md#рабочий-цикл). Игровые framework-механизмы, например app loader и Wulf/Scaleform factories, проверяйте по целевым исходникам при добавлении или изменении соответствующего вызова.

## Чистая логика и тесты

Применяйте общие правила тестирования из [SKILL.md](../SKILL.md#рабочий-цикл). Подходящие unit-тесты для Python-мода — самостоятельные вычисления и преобразования данных без импорта BigWorld/gui. Проверка внутри клиента описана в [runtime-validation.md](runtime-validation.md).

## Упаковка

`.wotmod` для World of Tanks и `.mtmod` для «Мира танков» — пакеты с `meta.xml` и runtime layout. Сверяйте путь entry и ресурсов после архивации. Версия должна быть одинаковой в имени артефакта, metadata и доступной моду runtime-константе. Не включайте исходники игры и локальные stubs.

Если мод использует конфиг, сохраняйте обратную совместимость формата или выполняйте явную миграцию. Не перезаписывайте пользовательские настройки дефолтами при каждом запуске.
