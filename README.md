# WoT Mod Development

Универсальный [Agent Skill](https://agentskills.io/) для разработки, обновления и диагностики клиентских модов **World of Tanks** и **«Мира танков»**.

Скилл следует открытому формату Agent Skills и не зависит от конкретной модели или агента. Его можно использовать в Claude Code, Codex и других клиентах, которые поддерживают `SKILL.md` напрямую или через [`skills` CLI](https://github.com/vercel-labs/skills).

## Установка

Рекомендуемый способ — универсальный установщик скиллов:

```bash
npx skills add wotstat/mods-development-skill -g
```

Установщик найдёт скилл и предложит выбрать доступных агентов. Флаг `-g` делает его доступным во всех проектах пользователя; без `-g` он устанавливается только для текущего проекта.

Для автоматической установки сразу в Claude Code и Codex:

```bash
npx skills add wotstat/mods-development-skill \
  --skill wot-mod-development \
  --global \
  --agent claude-code \
  --agent codex \
  --yes
```

## Использование

Скилл может активироваться автоматически по описанию задачи. Явный вызов зависит от агента:

| Агент | Вызов |
| --- | --- |
| Claude Code | `/wot-mod-development` |
| Codex | `$wot-mod-development` |

Пример задачи:

```text
Хочу сделать универсальный мод для World of Tanks и «Мира танков», который ...
```

## Документация для LLM

У документации WotStat есть специальные Markdown-представления для агентов:

- [`llms.txt`](https://docs.wotstat.info/llms.txt) — компактный индекс разделов с описаниями и прямыми ссылками на отдельные `.md`-страницы; это предпочтительная точка входа;
- [`llms-full.txt`](https://docs.wotstat.info/llms-full.txt) — вся русская документация одним большим файлом для сквозного поиска или подготовки офлайн-контекста.

Скилл направляет агента сначала в `llms.txt`, а затем только в нужные Markdown-страницы. Полный bundle не следует загружать без необходимости: он расходует существенно больше контекста. Документация помогает выбрать подход и инструменты, но клиентские API всё равно подтверждаются по целевой data-ветке `wot-src` и, когда возможно, в runtime.

## Для кого он нужен

- Автор-энтузиаст приходит с идеей и получает нормальную стартовую архитектуру, структуру проекта, точку входа, сборку и понятный путь до первого работающего результата.
- Опытный разработчик приносит существующий мод, который нужно адаптировать под новый патч, исправить или дополнить без незапрошенной перестройки всего проекта.

## Что меняет этот скилл

Скилл заставляет агента сначала установить технический контекст, а уже потом писать код:

- определить целевую игру: World of Tanks, «Мир танков» или обе;
- потребовать подходящую data-ветку [`wotstat/wot-src`](https://github.com/wotstat/wot-src) и проверять реальные игровые символы по исходникам;
- не выдумывать клиентские API, события, импорты и точки хуков;
- различать Python-only, Scaleform/AS3, Gameface/Unbound и resource-only моды;
- учитывать Python 2.7, структуру `.wotmod`/`.mtmod`, сборочные инструменты и ограничения конкретного UI-стека;
- проверять результат по ступеням: статические проверки, сборка, содержимое пакета, загрузка в клиент и ошибки в логах.

Отсутствие пригодных исходников игры блокирует реализацию кода, связанного с API клиента. Расхождение версии или билда исходников с клиентом не является автоматическим блокером: агент должен предупредить о нём, понизить уверенность и усилить runtime-проверку.

## Что подготовить перед работой

- проект мода или описание идеи;
- checkout подходящей data-ветки `wot-src` для каждой целевой игры;
- путь к установленному клиенту;
- версию и номер билда клиента, если они известны;
- необходимые компиляторы и сборочные инструменты.

В составе скилла есть необязательный read-only инспектор окружения:

```bash
python3 <skill-directory>/scripts/inspect_environment.py /path/to/mod \
  --source /path/to/wot-src \
  --game-dir /path/to/game \
  --expected-source-branch mt-ru
```

Помимо source gate инспектор статически проверяет VS Code/Pylance paths, stubs, рекомендации расширений и `asconfig.json`. Флаг `--strict-ide` возвращает exit code `3`, если IDE-конфигурация неполна. Это не заменяет живую проверку Problems/Output, hover, completion и AS3 Quick Compile в редакторе.

Актуальный источник можно получить так:

```bash
git clone --depth 1 --no-single-branch https://github.com/wotstat/wot-src.git
git -C wot-src switch mt-ru  # либо wot-eu, wot-na, wot-asia и т. д.
```

`main` в `wot-src` содержит publisher-код, а не исходники клиента. Конкретную data-ветку выбирают по продукту и региону; полный список приведён в README самого репозитория.

## Структура репозитория

- [`skills/wot-mod-development/SKILL.md`](skills/wot-mod-development/SKILL.md) — основные правила и маршрутизация;
- [`skills/wot-mod-development/references/`](skills/wot-mod-development/references/) — руководства для greenfield, существующих проектов, Python, Scaleform/AS3, Gameface и runtime-проверки;
- [`skills/wot-mod-development/scripts/inspect_environment.py`](skills/wot-mod-development/scripts/inspect_environment.py) — безопасная проверка проекта, исходников, клиента и статической IDE-конфигурации;
- [`skills/wot-mod-development/agents/openai.yaml`](skills/wot-mod-development/agents/openai.yaml) — необязательная UI-метадата Codex, не влияющая на другие агенты;
- [`tests/`](tests/) — тесты инспектора.

## Полезные ссылки

- [Документация по разработке модов](https://docs.wotstat.info/) — версия для человека
- [WotStat `wot-src`](https://github.com/wotstat/wot-src) — автоматически обновляемые data-ветки исходников и текстовых данных клиентов
- [WotStat REPL](https://github.com/wotstat/wotstat-repl) — desktop IDE, live Python 2.7 REPL и MCP для запуска клиента, логов, скриншотов и управляемых UI-проверок
- [Спецификация Agent Skills](https://agentskills.io/specification)
- [Установка через `skills` CLI](https://github.com/vercel-labs/skills)
- [Скиллы в Claude Code](https://code.claude.com/docs/en/skills)
- [Скиллы в Codex](https://developers.openai.com/codex/skills)

`wot-src`, игровые ресурсы и проприетарные инструменты в этот репозиторий не входят.
