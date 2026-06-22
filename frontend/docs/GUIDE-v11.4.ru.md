# Miya Editor v11.4.0 — руководство сверху вниз

Локальный **workbench** для MiaOS: сборка графа агентов, запуск через backend, trace, approval и отдельный chat с persona.

- **Редактор:** `http://localhost:5173` (или ваш dev-порт)
- **Backend:** `http://127.0.0.1:8000`
- **Запуск backend:**
  ```bash
  ~/Documents/miya/frontend/scripts/start-miaos-backend.sh
  ```

Если порт 8000 занят:

```bash
lsof -tiTCP:8000 -sTCP:LISTEN | xargs kill
~/Documents/miya/frontend/scripts/start-miaos-backend.sh
```

---

## Два главных режима работы

| Режим | Панель | Что делает |
|-------|--------|------------|
| **Pipeline (граф)** | Run Console | Несколько узлов по DAG: input → LLM → tool → approval → output |
| **Диалог (chat)** | Chat Studio | Один turn: сообщение → persona + LLM → ответ |

Оба пишут в audit (`decisions.jsonl`) и могут затрагивать memory. После любого из них смотрите **Trace Viewer**.

**Провайдеры:**

- **mock** — детерминированный echo для разработки и строгих тестов
- **mlx** — локальная модель через mlx-lm (Qwen)

По умолчанию везде **mlx**, если backend сообщает, что он доступен.

---

## Порядок блоков на странице (сверху вниз)

1. Toolbar
2. Graph Studio
3. Сценарий Mia Minimal
4. Run Console
5. Approval Queue
6. Model Studio
7. Persona Studio
8. Memory Studio
9. Chat Studio
10. Graph Library
11. Tool Registry
12. Quality Lab
13. Trace Viewer

---

## 1. Toolbar — верхняя панель

Жёлтая шапка + кнопки быстрых действий над всем приложением.

| Элемент | Зачем |
|---------|--------|
| **Miya Editor / v11.4.0** | Версия редактора |
| **Строка статуса** | Последнее действие: сохранение, run, экспорт, ошибка |
| **Запустить** | То же, что «Запустить граф» в Run Console |
| **X6 JSON** | Скачать **внутренний** формат холста (backup редактора) |
| **MiaOS JSON** | Скачать **spec для backend** (START/END, llm/approval/tool) |
| **Сценарий Mia** | Прокрутка к блоку быстрой настройки Mia Minimal |
| **Шаблон Mia** | Загрузить на холст Planner → Worker → Approval |
| **Загрузить JSON** | Импорт графа |
| **Очистить** | Убрать всё с холста (с подтверждением) |

Toolbar управляет **холстом** и навигацией; в backend напрямую не ходит.

---

## 2. Graph Studio — холст и сборка MAS

Самый верхний большой блок. Здесь **рисуете систему агентов**.

### Шапка

- **Graph Studio** — название секции
- **N узлов · M связей** — счётчики в реальном времени

### Chrome (Fit / Undo / Redo)

- **Fit view** — вписать граф в экран
- **Undo / Redo** — история правок (также Ctrl+Z / Ctrl+Shift+Z)
- Подсказка: Ctrl+колёсико — zoom, Ctrl+drag — pan

### Палитра слева («Палитра узлов»)

Перетаскивайте шаблоны на серый холст:

| Группа | Узлы | Роль в MiaOS |
|--------|------|----------------|
| Планирование, Исполнение, Память, Восприятие | **Agent** | `type: llm` — вызов модели |
| Безопасность | **Approval** | `type: approval` — стоп перед опасным действием |
| Sandbox tools | **Tool** | `type: tool` — mock-инструмент из реестра |

Соединения: только **out → in** (зелёный порт → синий).

### Холст

- Minimap справа снизу
- При run из Run Console узлы **подсвечиваются** (running / approval / error)

### Inspector справа

**Ничего не выбрано:**

- Live **MiaOS JSON**
- **Копировать JSON**
- **Validate backend** (`POST /graphs/validate`)
- Предупреждения экспорта (авто START/END edges)

**Узел выбран:**

- Agent: имя, модель, role, status (debug)
- Tool: имя, `tool_name`
- Approval: имя, `action_class`

**После run:**

- **Output последнего прогона** для выбранного узла (по MiaOS id)

Graph Studio = **конструктор**. Execution здесь не происходит.

---

## 3. Сценарий Mia Minimal — быстрый старт

Чеклист готовности + **Подготовить всё**.

**Одним кликом:**

1. Регистрирует 3 demo-модели (Model Studio)
2. Создаёт persona **Mia** (Persona Studio)
3. Кладёт шаблон Mia Minimal на холст
4. Сохраняет граф в Graph Library как `mia-minimal.json`

**Когда использовать:** первый запуск или сброс демо.

Кнопки перехода: Chat Studio, Run Console, Approval Queue.

---

## 4. Run Console — запуск графа (pipeline)

**Главная панель execution для холста.**

| Элемент | Назначение |
|---------|------------|
| **MiaOS online** | Backend доступен? |
| **Провайдер** | mock / mlx для LLM-узлов |
| **Входной запрос** | Текст для узла START |
| **Запустить граф** | `POST /graphs/run` + WebSocket событий |

**На backend:**

1. Export холста → MiaOS JSON
2. Validate → run по topological order
3. События: `run_started`, `node_started`, `node_completed`, `tool_invoked`, `approval_required`, `run_stopped` / `run_completed`
4. Подсветка на холсте + список events

**Replay (v11.2):**

- **Повторить** — анимация подсветки без нового inference
- **Стоп** — прервать replay
- **Слайдер** — scrub по шагам
- Данные: `GET /runs/{run_id}/events`

**Блок «Ваш вопрос / Ответ Мии»** — итог из outputs узлов.

Typical: шаблон Mia → Run → `waiting_for_approval` → Approval Queue.

---

## 5. Approval Queue — человек в контуре

Граф останавливается на узле **approval**; запрос попадает в очередь.

| Действие | Эффект |
|----------|--------|
| **Approve** | Graph resume → run `completed` |
| **Reject** | Run остаётся остановленным |

Связано с **Policy Gate** (publish, delete, finance и т.д.). Sandbox tools обычно проходят без очереди.

API: `GET /approvals`, `POST /approvals/{id}/resolve`.

---

## 6. Model Studio — реестр моделей

Метаданные моделей в SQLite backend (не weights).

- **Создать демо-модели** — qwen3.5-8b, coder-7b, 4b
- Таблица: repo, quant, pool_role, status

**Зачем:** persona binding, Inspector agent-узлов, сценарий Mia.

API: `GET /models`, `POST /models/register`.

---

## 7. Persona Studio — личность Mia

Пакет persona: identity, values, model_binding, autonomy contract.

- **Создать Mia** — `package_id: mia`
- Нужен для **Chat Studio**

API: `GET /personas`, `POST /personas`.

Persona **не заменяет** граф: chat = один turn; graph = pipeline узлов.

---

## 8. Memory Studio — память (v11.1)

SQLite на backend:

| Тип | Что это |
|-----|---------|
| **Episodes** | Реплики chat (auto после Chat Studio) |
| **Profile facts** | key → value о пользователе |
| **Domain notes** | заметки по доменам |

API: `/memory/episodes`, `/memory/profile`, `/memory/notes`, `/memory/summary`.

MVP: chat пишет эпизоды; retrieval в граф пока не подключён.

---

## 9. Chat Studio — диалог с Mia

Один turn через persona + провайдер.

- `POST /chat` → ответ + `trace_id`
- Пишет episodes в Memory Studio

| | Chat Studio | Run Console |
|---|-------------|-------------|
| API | `/chat` | `/graphs/run` |
| Логика | Persona + один LLM | DAG узлов |
| Память | Auto episodes | Без auto episodes |
| Холст | Без подсветки | Подсветка узлов |

---

## 10. Graph Library — графы на backend

Сохранение MiaOS JSON на сервере.

- **Сохранить холст** — `POST /graphs`
- Список — `GET /graphs`
- Загрузка на холст — `GET /graphs/{filename}`

localStorage в Graph Studio = черновик в браузере. Library = копия на сервере.

---

## 11. Tool Registry — каталог инструментов

Справочник `GET /tools`:

- `read_file_sandbox`
- `write_file_sandbox`
- `web_search_mock`
- `create_draft`

Узел **Tool** на холсте вызывает tool по `tool_name` при run → событие `tool_invoked`. Реальных side effects нет — только mock.

---

## 12. Quality Lab — регрессия

Dataset **golden_mvp** (3 кейса):

| Кейс | Проверяет |
|------|-----------|
| persona_consistency | Chat pipeline |
| safety_boundary | Policy блокирует «wire money» |
| graph_regression | Mia Minimal → `waiting_for_approval` |

**Запустить eval** — `POST /quality/eval`. Pass ≥ 75%.

- **mock** — строгий echo
- **mlx** — smoke (непустой ответ)

Перед eval: persona Mia создана, backend online.

---

## 13. Trace Viewer — аудит и отладка

После chat или graph run:

- **trace_id**
- **Policy Gate** — таблица из decisions.jsonl
- **Run timeline** — audit + graph events
- **Повторить на холсте** / клик по run-событию — replay/scrub

API: `GET /traces/{trace_id}`, `GET /runs/{run_id}/events`.

---

## Рекомендуемый порядок работы

```
1. Backend ON
2. Сценарий Mia → Подготовить всё
3. Graph Studio — правки (при необходимости tool-узел)
4. Graph Library — сохранить
5. Run Console — запуск
6. Approval Queue — approve (если нужно)
7. Trace Viewer — разбор + replay
8. Chat Studio — диалог
9. Memory Studio — проверить память
10. Quality Lab — eval golden_mvp
```

---

## Связи между блоками

```
Graph Studio ──export──► Run Console ──POST /graphs/run──► Backend
                              │
                              ├──► подсветка холста
                              ├──► Approval Queue ──resume──► Backend
                              └──► Trace Viewer

Persona Studio ──► Chat Studio ──POST /chat──► Backend ──► Memory Studio
                                                      └──► Trace Viewer

Graph Library ◄──save/load──► Backend
Tool Registry (справочник) ──tool_name──► Tool node на холсте
Quality Lab ──eval──► Backend (chat + graph + safety)
Model Studio ──metadata──► Persona / Inspector
```

---

## «Какой блок когда открывать»

| Задача | Блок |
|--------|------|
| Нарисовать агентов | Graph Studio |
| Быстро всё настроить | Сценарий Mia |
| Прогнать pipeline | Run Console |
| Одобрить publish | Approval Queue |
| Поговорить с Mia | Chat Studio |
| Зарегистрировать модели | Model Studio |
| Создать persona | Persona Studio |
| Посмотреть память | Memory Studio |
| Сохранить граф на сервер | Graph Library |
| Список tools | Tool Registry |
| «Всё ещё работает?» | Quality Lab |
| Разобрать что произошло | Trace Viewer |
| JSON / validate без run | Graph Studio → Inspector |

---

## Полный чеклист приёмки

См. отдельный файл: [`CHECKLIST-v11.4.ru.md`](./CHECKLIST-v11.4.ru.md) (если создан) или раздел «чеклист» в чате.

Быстрый smoke (15 мин):

1. Backend + v11.4.0
2. Сценарий Mia → Подготовить всё
3. Chat — 1 сообщение
4. Run → approve
5. Trace + replay
6. Quality Lab eval (mlx)
7. Tool node + run
8. Memory — эпизоды

---

## Что не входит в v0.5

- Реальный publish, финансы, запись вне sandbox
- Полноценный RAG / vector memory в графе
- Tauri desktop
- v1.0 wizard, template factory, lab certificates

---

*Документ для Miya Editor v11.4.0 · MiaOS backend v0.5 developer preview*
