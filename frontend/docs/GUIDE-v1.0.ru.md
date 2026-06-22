# Miya Editor v1.0.0 — v1.0 release guide

Локальный workbench для сборки, запуска и проверки MiaOS virtual personalities / MAS-графов.

## Запуск

```bash
~/Documents/miya/frontend/scripts/start-miaos-backend.sh
```

Редактор: `http://localhost:5173` · Backend: `http://127.0.0.1:8000`

## Порядок панелей

1. Toolbar
2. WelcomePanel
3. Runtime Profile
4. Graph Studio
5. Сценарий v1.0 Acceptance
6. Run Console
7. Approval Queue
8. Model Studio
9. Persona Studio
10. Memory Studio
11. Chat Studio
12. Template Registry
13. Graph Library
14. Tool Registry
15. Quality Lab
16. Trace Viewer

## Основной маршрут

1. Выберите **Runtime Profile**.
2. В **Model Studio** нажмите **Демо-модели** и выставьте lab cert при необходимости.
3. В **Persona Studio** создайте или импортируйте `.mia`.
4. В **Template Registry** выберите шаблон:
   - `mia-minimal` — базовый supervised pipeline.
   - `draft-with-tools` — `Web search` + `Draft` + approval.
   - `chat-memory-loop` — perception → memory → worker.
5. Нажмите **На холст** или **В Library**.
6. В **Run Console** запустите граф.
7. В **Approval Queue** одобрите `publish`.
8. Проверьте **Trace Viewer**, replay и Quality Lab.

## Graph Studio

Палитра должна содержать блоки:

- `START`, `END`
- `Планировщик`, `Исполнитель`, `Критик`, `Память`, `Восприятие`
- `Согласование`
- `Web search`, `Draft`, `Read file`, `Write file`

Русская памятка по смыслу блоков: [`BLOCKS-RU.md`](./BLOCKS-RU.md).

MiaOS JSON поддерживает типы:

- `input`
- `llm`
- `critic`
- `tool`
- `approval`
- `output`

## Backend endpoints v1.0

- `GET /runtime/profiles`
- `GET /models/compatibility`
- `PATCH /models/{id}/lab-cert`
- `DELETE /models/demo`
- `GET /personas/{package_id}/export`
- `POST /personas/import`
- `GET /templates`
- `GET /templates/{template_id}`
- `POST /templates/{template_id}/instantiate`

Полный чеклист: [`CHECKLIST-v1.0.ru.md`](./CHECKLIST-v1.0.ru.md).
