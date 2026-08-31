# Scaleform / Flash / AS3

Читайте только когда проект использует `.as`, `.swf`, Scaleform или `as3/`. Базовая настройка: <https://docs.wotstat.info/guide/first-steps/environment/as3/index.md>. Теория: <https://docs.wotstat.info/guide/scripting/as3-theory/index.md>.

## Toolchain gate

Кроме готового Python-окружения проверьте:

- JDK, совместимый с используемыми AS3 tools;
- AIR SDK для editor tooling, если оно используется;
- Apache Royale distribution с поддержкой JS/SWF, не JS-only;
- game SWC libraries, извлечённые из точного целевого клиента;
- подходящий `playerglobal.swc`;
- реальные пути compiler и libraries в `asconfig.json`/`build-config.xml`.

WotStat сейчас описывает JDK 11+, AIR SDK Manager и Apache Royale JS/SWF. Проверяйте актуальную страницу перед установкой: tool versions меняются.

SWC и декомпилированный AS3 относятся к конкретному продукту/патчу. Не используйте SWC от «Мир танков» как доказательство WoT-совместимости. Не коммитьте и не публикуйте извлечённые game libraries без подтверждённого права.

## `asconfig.json` и готовность IDE

Разделяйте два независимых контура:

- ActionScript & MXML extension, Quick Compile и `asconfigc` читают `asconfig.json`;
- release-сборка проекта может читать `build-config.xml` или другой build config.

Прохождение одного контура не подтверждает второй. Для нового Apache Royale/SWF target явно задайте в `asconfig.json`:

```jsonc
{
  "config": "royale",
  "compilerOptions": {
    "targets": ["SWF"],
    "target-player": "17.0", // пример: подставьте проверенную версию
    "swf-version": 17,       // пример: подставьте совместимый номер
    "source-path": ["src"],
    "external-library-path": ["libs/...", "libs/playerglobal.swc"],
    "output": "bin/example.swf"
  },
  "mainClass": "author.mod.Example"
}
```

`mainClass` должен быть полным class name, реально разрешаемым через `source-path`; не оставляйте шаблонный `Main`, если такого класса нет. Каждый source/library path должен существовать. `target-player` должен соответствовать доступному каталогу `playerglobal` в SDK либо явно подключённому совместимому `playerglobal.swc`; `swf-version` берите из проверенной конфигурации целевого клиента/toolchain, а не угадывайте. Значения в `asconfig.json` и release config должны совпадать.

Для нескольких SWF создавайте явный config/task на каждый entry и output. Не заставляйте существующий AIR/Flex/Animate-проект переходить на Royale только ради унификации: сохраните доказанную toolchain и проверьте её собственную конфигурацию.

IDE gate для AS3 пройден, когда:

1. `asconfig.json` проходит schema validation;
2. editor разрешает `flash.*`, игровые `net.wg.*` и собственный package на representative-файле;
3. `asconfigc` или VS Code Quick Compile собирает target без missing SDK/library/mainClass errors;
4. Problems и ActionScript language-server Output проверены после перезапуска/индексации;
5. отдельно проходит release-сборка, а её `target-player`, `swf-version`, libraries, entry и output согласованы с editor config.

## Layout и граница Python/AS3

Обычно AS3 source, libs и build output живут вне `res`, а готовый `.swf` попадает в runtime `res/gui/flash`. Поддерживайте один явный controller boundary:

- Python регистрирует view по source-backed framework API и управляет lifecycle;
- AS3 отвечает за display objects, presentation и вызовы через подтверждённый bridge;
- linkage/view ids имеют уникальный namespace.

Не копируйте `ViewSettings`, factory registration или layer constants из примера другого патча. Проверьте их определения и игровые аналоги в `sources/`, `sources-as3/` и SWC целевого клиента.

## Build

AS3 compiler failure должен останавливать общую сборку. Перед компиляцией очищайте только выделенный output-каталог. Проверяйте, что:

- каждый заявленный SWF действительно создан;
- в `.wotmod`/`.mtmod` находится ожидаемый `res/gui/flash/<name>.swf`;
- package/class names соответствуют linkage;
- debug artifacts и SWC не попали в пакет.

Для нескольких SWF задайте явный список targets. Не полагайтесь на случайный glob, который может оставить stale output.

## Runtime-проверка

Сначала подтвердите Python registration/load, затем AS3 construction/populate, затем передачу данных. Проверяйте закрытие/уничтожение view и отсутствие повторной регистрации после смены app/context.

Визуально проверьте как минимум разные разрешения/UI scale, длинную локализацию, повторное открытие и переходы между ангаром/боем, если они входят в scope. Для battle overlay используйте replay, тренировочную комнату или тестовый режим.
