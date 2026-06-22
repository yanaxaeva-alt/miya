# Чеклист приёмки Miya Editor v1.0.0

Версия редактора: **v1.0.0** · Backend: `http://127.0.0.1:8000`

## 0. Подготовка

- [ ] `~/Documents/miya/frontend/scripts/start-miaos-backend.sh`
- [ ] Toolbar показывает **v1.0.0**
- [ ] `GET /health` → `{"status":"ok"}`
- [ ] Hard refresh браузера

## 1. First Run / Runtime

- [ ] WelcomePanel видит backend
- [ ] Runtime Profile выбран (`macbook_air_m4_32gb` или `macbook_pro_m4pro_48gb`)
- [ ] Model Studio показывает compatibility и lab cert dropdown

## 2. Graph Studio

- [ ] Палитра содержит `START`, `END`, `Критик`
- [ ] Палитра tools содержит `Web search`, `Draft`, `Read file`, `Write file`
- [ ] Inspector показывает JSON и Validate backend
- [ ] MiaOS JSON содержит `input`, `llm/critic`, `tool`, `approval`, `output`

## 3. Template Registry

- [ ] `GET /templates` отдаёт `mia-minimal`, `draft-with-tools`, `chat-memory-loop`
- [ ] `mia-minimal` → **На холст**
- [ ] `draft-with-tools` → **На холст** показывает `Web search` и `Draft`
- [ ] Любой шаблон → **В Library**

## 4. Persona / Memory / Chat

- [ ] Persona Studio создаёт Mia
- [ ] Export `.mia.zip`
- [ ] Import `.mia.zip` с новым `package_id`
- [ ] Chat Studio создаёт trace и Memory episodes

## 5. Run / Approval / Trace

- [ ] Run Console запускает graph
- [ ] Approval Queue показывает `publish`
- [ ] Approve переводит run в `completed`
- [ ] Trace Viewer показывает policy/timeline
- [ ] Replay/Повторить на холсте работает

## 6. Quality / Tools

- [ ] Tool Registry показывает 4 sandbox tools
- [ ] Tool node run создаёт `tool_invoked`
- [ ] Quality Lab `golden_mvp` проходит gate

## Smoke

```bash
curl -s http://127.0.0.1:8000/templates
curl -s http://127.0.0.1:8000/models/compatibility?profile_name=macbook_air_m4_32gb
curl -s http://127.0.0.1:8000/tools
curl -s http://127.0.0.1:8000/graphs
```
