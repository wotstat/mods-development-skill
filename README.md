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

## Для кого он нужен

- Автор-энтузиаст приходит с идеей и получает нормальную стартовую архитектуру, структуру проекта, точку входа, сборку и понятный путь до первого работающего результата.
- Опытный разработчик приносит существующий мод, который нужно адаптировать под новый патч, исправить или дополнить без незапрошенной перестройки всего проекта.

## Что меняет этот скилл

Скилл заставляет агента сначала установить технический контекст, а уже потом писать код:

- определить целевую игру: World of Tanks, «Мир танков» или обе;
- потребовать подходящий checkout `wot-src` и проверять реальные игровые символы по исходникам;
- не выдумывать клиентские API, события, импорты и точки хуков;
- различать Python-only, Scaleform/AS3, Gameface/Unbound и resource-only моды;
- учитывать Python 2.7, структуру `.mtmod`, сборочные инструменты и ограничения конкретного UI-стека;
- проверять результат по ступеням: статические проверки, сборка, содержимое пакета, загрузка в клиент и ошибки в логах.

Отсутствие пригодных исходников игры блокирует реализацию кода, связанного с API клиента. Расхождение версии или билда исходников с клиентом не является автоматическим блокером: агент должен предупредить о нём, понизить уверенность и усилить runtime-проверку.

## Что подготовить перед работой

- проект мода или описание идеи;
- checkout `wot-src` для каждой целевой игры;
- путь к установленному клиенту;
- версию и номер билда клиента, если они известны;
- необходимые компиляторы и сборочные инструменты.

В составе скилла есть необязательный read-only инспектор окружения:

```bash
python3 <skill-directory>/scripts/inspect_environment.py /path/to/mod \
  --source /path/to/wot-src \
  --game-dir /path/to/game
```

## Структура репозитория

- [`skills/wot-mod-development/SKILL.md`](skills/wot-mod-development/SKILL.md) — основные правила и маршрутизация;
- [`skills/wot-mod-development/references/`](skills/wot-mod-development/references/) — руководства для greenfield, существующих проектов, Python, Scaleform/AS3, Gameface и runtime-проверки;
- [`skills/wot-mod-development/scripts/inspect_environment.py`](skills/wot-mod-development/scripts/inspect_environment.py) — безопасная проверка проекта, исходников и клиента;
- [`skills/wot-mod-development/agents/openai.yaml`](skills/wot-mod-development/agents/openai.yaml) — необязательная UI-метадата Codex, не влияющая на другие агенты;
- [`tests/`](tests/) — тесты инспектора.

## Полезные ссылки

- [Документация по разработке модов](https://docs.wotstat.info/)
- [Fuflo WoT REPL](https://github.com/Newmcpe/fuflo-wot-repl) — MCP REPL для диагностических команд в запущенном клиенте и чтения логов
- [Спецификация Agent Skills](https://agentskills.io/specification)
- [Установка через `skills` CLI](https://github.com/vercel-labs/skills)
- [Скиллы в Claude Code](https://code.claude.com/docs/en/skills)
- [Скиллы в Codex](https://developers.openai.com/codex/skills)

`wot-src`, игровые ресурсы и проприетарные инструменты в этот репозиторий не входят.
