# Чеклист приёмки Miya Editor v11.4.0

Версия редактора: **v11.4.0** · Backend: `http://127.0.0.1:8000`

Подробное описание блоков: [`GUIDE-v11.4.ru.md`](./GUIDE-v11.4.ru.md)

---

## 0. Подготовка

- [ ] `~/Documents/miya/frontend/scripts/start-miaos-backend.sh` — Uvicorn на :8000
- [ ] Редактор открыт, toolbar **v11.4.0**
- [ ] `curl -s http://127.0.0.1:8000/health` → `{"status":"ok"}`
- [ ] `curl -s http://127.0.0.1:8000/providers` → mock + mlx
- [ ] Hard refresh (Cmd+Shift+R)

---

## 1. Toolbar

- [ ] Запустить → run из Run Console
- [ ] MiaOS JSON → скачивание spec
- [ ] Шаблон Mia → 3 узла на холсте
- [ ] Сценарий Mia → scroll к сценарию

---

## 2. Graph Studio

- [ ] Счётчики узлов/связей
- [ ] Fit view, Undo, Redo
- [ ] Палитра: agent, approval, tool
- [ ] Inspector: JSON + Validate backend
- [ ] Run → подсветка узлов
- [ ] Replay: Повторить + scrub
- [ ] Inspector: output после run

---

## 3. Сценарий Mia

- [ ] Подготовить всё — без ошибок
- [ ] Чеклист зелёный (после run)

---

## 4. Run Console

- [ ] MiaOS online
- [ ] Run → `waiting_for_approval` (шаблон Mia)
- [ ] Events + Q&A блок

---

## 5. Approval Queue

- [ ] Approve → run `completed`

---

## 6. Model / Persona

- [ ] 3 demo models
- [ ] Persona Mia создана

---

## 7. Memory

- [ ] Chat → episodes
- [ ] Profile fact / domain note

---

## 8. Chat Studio

- [ ] mlx, ответ + trace_id

---

## 9. Graph Library

- [ ] Save / list / load

---

## 10. Tool Registry

- [ ] 4 tools, без 500
- [ ] Tool node на холсте → `tool_invoked`

---

## 11. Quality Lab

- [ ] golden_mvp eval ≥ 75% (mlx)

---

## 12. Trace Viewer

- [ ] Policy Gate + timeline
- [ ] Повторить на холсте

---

## Backend smoke

```bash
curl -s http://127.0.0.1:8000/tools
curl -s "http://127.0.0.1:8000/memory/summary?package_id=mia"
curl -s http://127.0.0.1:8000/quality/datasets
curl -s http://127.0.0.1:8000/graphs
```

---

## Тесты (опционально)

```bash
cd ~/Documents/miya && uv run pytest tests/unit -q
cd ~/Documents/miya/frontend && npm run build
```

---

## Типичные проблемы

| Симптом | Решение |
|---------|---------|
| Tool Registry 500 | Restart backend |
| :8000 busy | `lsof -tiTCP:8000 -sTCP:LISTEN \| xargs kill` |
| MLX unavailable | `MIYA_WITH_MLX=1` + restart script |
| Quality mock fail | Использовать mock provider в eval |
