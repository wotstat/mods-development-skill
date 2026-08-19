# Runtime validation и Fuflo WoT REPL

Читайте при диагностике живого клиента, smoke-тестах, работе с логами или настройке MCP.

Рекомендуемый инструмент: [Fuflo WoT REPL](https://github.com/Newmcpe/fuflo-wot-repl). Он поддерживает WoT и «Мир танков», выполняет Python 2.7 на main game thread, читает stdout/stderr/BigWorld logs, генерирует stubs живых объектов и предоставляет локальный MCP server.

Runtime-интроспекция дополняет, но не отменяет matching `wot-src`: REPL показывает фактический объект, а исходники объясняют lifecycle и callers.

## Подключение

Следуйте актуальному README/release репозитория. В текущей версии локальный MCP URL содержит постоянный token и может быть добавлен в Codex командой, показанной в README. Не копируйте token в issue, commit, лог ответа или публичный config. При работе на одной машине предпочитайте loopback URL. Сетевой доступ открывайте только осознанно и с подходящими firewall controls.

Если MCP tools уже доступны, начинайте с read-only discovery. Текущий сервер предоставляет:

- `wot_list_clients` — установки и статусы;
- `wot_start_client` — установить/connect agent и запустить клиент/replay;
- `wot_exec` — выполнить Python 2.7 на main thread;
- `wot_read_log` — читать новые log records по cursor;
- `wot_close_client` — корректно закрыть клиент;
- `wot_kill_client` — принудительно завершить проверенный процесс.

Перед вызовом сверяйте актуальную tool schema, а не полагайтесь на этот список.

## Безопасный цикл

1. Зафиксируйте target product/version/path и вызовите client listing.
2. Получите baseline log cursor или timestamp; не очищайте весь пользовательский log.
3. Подключитесь к уже запущенному целевому клиенту либо запустите явно выбранный client/replay.
4. Сопоставьте source commit с версией реально запущенного клиента и зафиксируйте расхождение; mismatch не останавливает тест.
5. Сначала выполните read-only probe: импорт, наличие symbol, тип, signature/doc, lifecycle state.
6. Соберите/установите тестовый `.mtmod` обычным project workflow. Не предполагайте, что установка REPL agent устанавливает пользовательский мод.
7. Выполните один ограниченный behavior probe или пользовательский сценарий.
8. Прочитайте только новые logs по cursor; ищите уникальный mod prefix, traceback, ERROR/WARNING.
9. Повторите после минимального изменения. Закройте клиент корректно только если это входит в задачу.

`wot_exec` работает на main thread: не запускайте там долгие циклы, blocking I/O, ожидание или тяжёлую обработку. Используйте короткий timeout и маленькие probes. Не вызывайте gameplay actions в публичном бою и не автоматизируйте игру вместо проверки мода.

`wot_kill_client` — последний вариант после неудачи graceful close и только в разрешённом scope. Потеря несохранённого state пользователя возможна.

## Что проверять

Минимальный smoke test:

- package обнаружен loader-ом;
- entry завершился без traceback;
- ожидаемые subscriptions/registrations установлены один раз;
- feature выдаёт безопасный наблюдаемый marker;
- после действия нет новых ошибок;
- повторный вход в context не дублирует hook/listener.

Для patch migration добавьте probes изменившихся signatures и lifecycle state. Для Scaleform проверяйте Python registration, создание view и bridge. Для Gameface — resource id, создание view/model, engine readiness, JS/Python command roundtrip и cleanup.

## Сценарии боя

Предпочитайте replay для воспроизводимости. Если replay недостаточен, используйте тренировочную комнату, тестовый сервер или «Полигон». Записывайте точные шаги, карту/режим и момент ожидаемого поведения, чтобы следующий прогон был сопоставим.

Итоговое утверждение различайте явно:

- **source-backed** — решение основано на доступных исходниках с указанной версией;
- **exact-source-verified** — API подтверждён checkout той же версии/build;
- **build-verified** — compiler и package checks прошли;
- **load-verified** — клиент загрузил мод без новых ошибок;
- **behavior-verified** — целевой runtime scenario наблюдался;
- **cross-product verified** — предыдущие проверки отдельно прошли для каждой заявленной цели.
