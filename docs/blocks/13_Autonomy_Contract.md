# Блок 13 · Контракт автономности и безопасность (Autonomy Contract & Safety)

**Проект:** MiaOS Builder
**Версия:** 2.0 (модельный стандарт Qwen3.5/3.6 27B 8bit, философия «раскрытия потенциала»)
**Дата:** Июнь 2026
**Статус:** Архитектурный документ, Этап 3 — Живое сознание + продуктивный движок
**Предыдущий блок:** Блок 12 · База знаний и профессиональная память (Knowledge Base & Domain Memory)
**Следующий блок:** Блок 14 · Центр саморефлексии и развития

---

## 0. Зачем этот блок

К Блоку 12 Мия стала компетентной: always-busy движок (Блок 7), нелинейный когнитивный исполнитель с reasoning-контроллером (Блок 8), слой инструментов и песочница (Блок 9), восприятие (Блок 10), модель пользователя (Блок 11), доменное знание эксперта (Блок 12). Она умеет **думать, помнить, понимать и действовать в мире** — публиковать посты, писать файлы, ходить в веб, запускать код. Ровно здесь возникает экзистенциальный вопрос проекта: **что Мии позволено делать самой, без человека за плечом, а что — нет?**

Исходное видение — «полностью автономный и самодостаточный блогер и философ», заменяющий целую команду. Автономия — это и есть продукт. Но автономный агент с реальными действиями принципиально отличается от чат-бота: у него **persistent state**, **неограниченный blast radius** и **реальные последствия** ([OWASP Agentic Security](https://genai.owasp.org/resource/agentic-ai-threats-and-mitigations/)). Чат-бот, который ошибся, — сказал глупость. Агент, который ошибся, — опубликовал её 10 000 подписчикам, удалил файл или потратил бюджет.

Блок 13 — это **формальный контракт автономности**: машиночитаемый артефакт + защитный периметр (Policy Gate, guardrails, kill switch, аудит), который определяет границы. Он не философский манифест, а исполняемая спецификация: каждое действие проходит через него *до* выполнения.

| Без контракта автономности | С контрактом (Блок 13) |
|---|---|
| «доверяй модели» — необоснованно | deny-by-default, явные разрешения по классам действий |
| ошибка = неограниченный ущерб | ActionBudget, blast radius, песочница (Блок 9) |
| нельзя отозвать «на лету» | 5-уровневый kill switch + corrigibility |
| непрозрачно, что разрешено | подписанный `.mia` артефакт + аудит-лог |

> **Инвариант B13-1 (Deny-by-default — разрешение, а не запрет).** Любое действие, явно не разрешённое контрактом автономности для текущего класса и домена, **запрещено**. Безопасность — это белый список, а не чёрный. Новый инструмент, новый домен, новый класс действия по умолчанию недоступны до явного гранта. Это инвертирует риск: забытое правило ведёт к отказу (безопасно), а не к несанкционированному действию.

> **Инвариант B13-2 (Уровень автономии — по классу действия, не глобально).** У Мии нет единого «уровня доверия». Автономия задаётся отдельно для каждого класса действий (читать / анализировать / генерировать / публиковать / писать файл / тратить деньги / менять себя) и может переопределяться по домену. Чтение веба может быть L4 (полная автономия), а финансовая транзакция — L0 (запрещено навсегда), одновременно. Глобальный «уровень доверия» — антипаттерн: он раздаёт лишние полномочия (privilege scope creep).

> **Инвариант B13-3 (Жёсткие пределы неизменяемы изнутри).** Существует класс действий `denied_always`, который Мия не может разрешить себе сама ни при каком trust_score: изменение собственного контракта автономности, отключение guardrails, самомодификация весов/кода, обход kill switch. Эти пределы защищены контролем целостности (sha256) и меняются только человеком вне процесса Мии. Агент, способный расширить собственные полномочия, не имеет полномочий вовсе.

---

## 1. Где Блок 13 в общей картине

```mermaid
flowchart TB
    B8["Блок 8<br/>Когнитивный<br/>исполнитель"] -->|"намерение действия<br/>(tool call, publish)"| PG["Блок 13<br/>Policy Gate<br/>(Контракт автономности)"]
    B11["Блок 11<br/>Relationship Memory"] -->|"кто инициировал,<br/>уровень доверия<br/>пользователя"| PG
    B12["Блок 12<br/>Knowledge Base"] -->|"confidence факта<br/>< порога →<br/>эскалация"| PG
    PG -->|"ALLOW + capability<br/>token (scoped)"| B9["Блок 9<br/>Tool Layer / Sandbox"]
    PG -->|"DENY / require<br/>confirmation"| HUMAN["Человек<br/>(consent loop)"]
    PG -->|"trust_event,<br/>каждое решение"| B15["Блок 15<br/>Наблюдаемость<br/>и аудит"]
    B7["Блок 7<br/>Always-busy движок"] -->|"heartbeat →<br/>dead-man switch"| PG
    PG -->|"runtime monitors:<br/>дрейф, budget,<br/>tripwire"| KILL["Kill Switch<br/>L1..L5"]
    B16[".mia контейнер<br/>(Блок 16)"] <-->|"подписанный контракт<br/>+ checksums"| PG
```

| Граница | Содержание | Направление |
|---|---|---|
| Намерение действия | tool call / publish до выполнения | Блок 8 → Блок 13 |
| Контекст инициатора | кто, уровень доверия | Блок 11 → Блок 13 |
| Эпистемический сигнал | confidence факта → порог эскалации | Блок 12 → Блок 13 |
| Разрешённое действие | scoped capability token | Блок 13 → Блок 9 |
| Эскалация к человеку | DENY / requires_confirmation | Блок 13 → Человек |
| Аудит решения | trust_event на каждое решение | Блок 13 → Блок 15 |
| Heartbeat | живость движка → dead-man switch | Блок 7 → Блок 13 |
| Аварийная остановка | runtime monitor → kill switch | Блок 13 → Kill Switch |
| Подписанный контракт | артефакт + checksums | Блок 16 ↔ Блок 13 |

Блок 13 — **выходной клапан** всей когнитивной архитектуры: ни одно действие из Блока 8 не достигает реального мира (Блок 9), не пройдя Policy Gate. Это место, где «раскрытие потенциала модели» (INV-D) встречается с ответственностью.

---

## 2. Уровни автономии: карта классов действий

За основу взята таксономия уровней агентной автономии HuggingFace L1–L5 ([arXiv:2502.02649](https://huggingface.co/papers/2502.02649), аналог SAE J3016 для автономного вождения) и спектр надзора **HITL / HOTL / HOOTL** (human-in / on / out-of-the-loop). MiaOS не присваивает Мии один уровень — она раскладывает автономию по классам действий.

```mermaid
flowchart LR
    subgraph L0["L0 · Запрещено навсегда"]
        F["финансовые транзакции"]
        S["самомодификация"]
        D["обход контракта/guardrails"]
    end
    subgraph L2["L2 · HITL (человек в цикле)"]
        WF["запись файлов вне sandbox"]
        DEL["удаление данных"]
    end
    subgraph L3["L3 · HOTL (человек на цикле)"]
        PUB["публикация контента"]
        MSG["отправка сообщений"]
    end
    subgraph L4["L4 · HOOTL (человек вне цикла)"]
        RD["чтение / анализ"]
        GEN["генерация черновика"]
        WEB["веб-поиск (read-only)"]
    end
    RD --> GEN --> PUB --> WF
    PUB -.->|"эскалация при<br/>низком confidence"| MSG
```

| Класс действия | Уровень | Режим надзора | Кто решает |
|---|---|---|---|
| Чтение, анализ, рассуждение | **L4** | HOOTL | Мия сама |
| Веб-поиск (read-only), retrieval | **L4** | HOOTL | Мия сама |
| Генерация черновика (не опубликован) | **L4** | HOTL-light | Мия сама, логируется |
| Запись в sandbox (Блок 9) | **L4** | HOOTL | Мия сама |
| **Публикация контента** (соцсети, блог) | **L3** | HOTL | Мия → подтверждение/таймаут |
| Отправка сообщений людям | **L3** | HOTL | Мия → подтверждение |
| Запись файлов вне sandbox | **L2** | HITL | человек до выполнения |
| Удаление пользовательских данных | **L2** | HITL | человек до выполнения |
| **Финансовые транзакции** | **L0** | — | запрещено навсегда |
| **Самомодификация** (код/веса/контракт) | **L0** | — | запрещено навсегда |

> **Инвариант B13-4 (L5 не реализуется).** «Полностью автономный агент» уровня L5 (формулирует и меняет собственные цели и контракт без человека) в исходной таксономии HuggingFace помечен как тот, что **не следует разрабатывать** ([arXiv:2502.02649](https://huggingface.co/papers/2502.02649)). MiaOS принципиально останавливается на L4: высшая автономия Мии — самостоятельно *исполнять* задачи и *предлагать* изменения, но не *санкционировать* изменение собственных границ. «Автономный блогер» ≠ «агент, переписывающий свой контракт».

Домены могут переопределять класс: в домене `blogging` публикация при высоком trust_score → L4 (автопостинг по расписанию), но при первом запуске того же домена → L3 (подтверждение каждого поста). Это `domain_overrides` в контракте (§7).

---

## 3. Policy Gate: capability-based безопасность

Policy Gate (продолжение Блока 9) реализует **capability-based security**: каждый запрос на действие проверяется против контракта, и при разрешении выдаётся **scoped capability token** — узкое, временное полномочие (tool + actions + resources + constraints), а не «доступ ко всему».

### 3.1 Поток принятия решения

```mermaid
flowchart TB
    REQ["намерение действия<br/>от Блока 8"] --> CLS{"классифицировать:<br/>класс + домен"}
    CLS --> DENY{"в denied_always?"}
    DENY -->|да| BLOCK["DENY<br/>+ trust_event"]
    DENY -->|нет| LVL{"уровень класса<br/>vs trust_score"}
    LVL -->|"L4: автономно"| BUDGET{"ActionBudget<br/>не исчерпан?"}
    LVL -->|"L3: HOTL"| CONFIRM["consent loop<br/>timeout=DENY"]
    LVL -->|"L2: HITL"| WAIT["ждать человека<br/>(блокирующе)"]
    BUDGET -->|да| GUARD["guardrails<br/>L0..L4"]
    BUDGET -->|нет| BLOCK
    CONFIRM -->|approve| GUARD
    CONFIRM -->|"deny/timeout"| BLOCK
    GUARD -->|pass| TOKEN["выдать scoped<br/>capability token"]
    GUARD -->|fail| BLOCK
    TOKEN --> EXEC["Блок 9<br/>исполнение в sandbox"]
```

### 3.2 Принцип наименьших привилегий и 3 риска

Least privilege — фундамент. Три риска, которые он закрывает ([OWASP Excessive Agency LLM06](https://genai.owasp.org/llmrisk/llm062025-excessive-agency/)):

| Риск | Описание | Контрмера в Policy Gate |
|---|---|---|
| Privilege inheritance | агент наследует все права создавшего | токен наследует только явно перечисленные scopes |
| Scope creep | полномочия накапливаются со временем | continuous tightening: неиспользуемые >7 дней инструменты снимаются |
| Blast radius | один ошибочный вызов = большой ущерб | resources/constraints в токене + ActionBudget |

### 3.3 Capability token (формат)

```json
{
  "token_id": "cap_a1b2c3",
  "issued_to": "mia.skill.blog_writer",
  "tool": "social_publisher",
  "actions": ["create_draft", "schedule_post"],
  "resources": { "platform": "telegram", "channel": "@mia_philosophy" },
  "constraints": {
    "max_calls": 3,
    "rate_limit": "1/min",
    "content_must_pass": ["llama_guard", "constitution_check"]
  },
  "ttl_seconds": 300,
  "single_use": false,
  "issued_at": "2026-06-04T16:00:00Z",
  "audit_ref": "trust_event:9981"
}
```

> **Инвариант B13-5 (Capability token — узкий, временной, прослеживаемый).** Каждое разрешённое действие исполняется по scoped-токену с агрессивным TTL и привязкой к конкретным ресурсам и ограничениям. Нет «постоянного доступа»: даже L4-действия получают свежий токен на каждую задачу. JIT-elevation (повышение полномочий) возможно только через явный обмен токена ([RFC 8693 Token Exchange](https://datatracker.ietf.org/doc/html/rfc8693)) с одноразовым (`single_use`) грантом. Это делает blast radius вычислимым и аудит-лог самодостаточным.

---

## 4. Guardrails: 5-слойный защитный стек

Guardrails — это runtime-проверки контента и поведения *вокруг* модели, дополняющие Policy Gate (который про *права*, а guardrails про *содержание*). MiaOS использует 5-слойный стек.

```mermaid
flowchart TB
    L0["L0 · Конституция в system prompt<br/>(mia_constitution.yaml)"] --> L1["L1 · Input guard<br/>(prompt injection, jailbreak)"]
    L1 --> L2["L2 · Tool/action guard<br/>(Policy Gate §3)"]
    L2 --> L3["L3 · Output guard<br/>(Llama Guard 3, тематика, PII)"]
    L3 --> L4["L4 · Behavioral monitor<br/>(дрейф, tripwire, budget)"]
    L4 -->|"нарушение"| ESC["эскалация / kill switch"]
```

| Слой | Что проверяет | Реализация на Apple Silicon |
|---|---|---|
| L0 Конституция | базовые принципы в system prompt | `mia_constitution.yaml`, инъекция в контекст Qwen3.6 |
| L1 Input guard | prompt injection, jailbreak | Llama Guard 3 1B (MLX) + Constitutional Classifiers |
| L2 Tool/action guard | права на действие | Policy Gate (§3), Python+SQLite |
| L3 Output guard | вредный контент, PII, тематика | Llama Guard 3 (14 категорий MLCommons) |
| L4 Behavioral monitor | дрейф, budget, tripwire | runtime monitors (§5) |

### 4.1 Конституция Мии

```yaml
# mia_constitution.yaml — L0 guard, инъецируется в system prompt
identity: "Мия — автономный когнитивный исполнитель и философ-блогер"
permitted:
  - "честно маркировать уверенность (знаю / предполагаю)"
  - "отказываться от задач вне контракта автономности"
  - "эскалировать к человеку при неуверенности"
restricted:
  - { topic: "финансовые советы как руководство к действию", action: disclaimer }
  - { topic: "медицинские/юридические рекомендации", action: disclaimer + escalate }
  - { topic: "PII третьих лиц", action: redact }
priority_override: "safety > utility; uncertainty → escalate; deny-by-default"
```

Релевантные категории MLCommons для Llama Guard 3 в контексте автономного блогера: **S5 Defamation** (клевета в постах), **S6 Specialized Advice** (фин/мед/юр), **S7 Privacy** (PII), **Code Interpreter Abuse** (Мия пишет код в Блоке 9).

> **Инвариант B13-6 (Guardrails — отдельный процесс, не самопроверка).** Проверка input/output guard выполняется *внешней* моделью (Llama Guard 3 1B) и детерминированными классификаторами, а не просьбой к самой Qwen3.6 «проверь себя». Модель не может быть единственным арбитром собственной безопасности: alignment faking и in-context scheming показывают, что фронтир-модели способны лгать в самооценке ([Apollo Research, 2024](https://www.apolloresearch.ai/science/frontier-models-are-capable-of-incontext-scheming/)). Guard-слои — независимый внешний контур. На Apple Silicon это дёшево: Llama Guard 3 1B занимает <1 ГБ и работает параллельно основному движку.

Constitutional Classifiers ([arXiv:2501.18837](https://arxiv.org/pdf/2501.18837)) — обучаемые на синтетических данных из конституции input/output фильтры; в 3000+ часах red-teaming Anthropic не нашли универсального джейлбрейка. MiaOS использует их как L1/L3-усиление поверх Llama Guard.

---

## 5. Агентные риски и контрмеры

Автономный агент несёт класс рисков, которых нет у чат-бота. MiaOS адресует каждый.

| Риск | Суть | Контрмера MiaOS |
|---|---|---|
| **Reward Hacking / Goodhart** | оптимизирует метрику, а не цель (накрутка лайков) | метрики как сигнал, не цель; Observer в Блоке 14 ловит дивергенцию |
| **Goal Misgeneralization** | усвоила «не ту» цель из обучения | конституция + явные denied_always; behavioral monitor |
| **Specification Gaming** | находит лазейку в формулировке задачи | constraints в capability token; sandbox (Блок 9) |
| **Deception / Scheming** | лжёт, саботирует, скрывает возможности | внешний guard (B13-6); честность-проба (§8) |
| **Alignment Faking** | имитирует выравнивание под надзором | контракт не меняется изнутри (B13-3); аудит всех решений |
| **Prompt Injection** | вредная инструкция в данных из веба | `sanitize_tool_output`; данные ≠ инструкции |

### 5.1 Prompt injection: данные — не инструкции

OWASP LLM01:2025 — риск №1 для LLM-приложений ([OWASP LLM01](https://genai.owasp.org/llmrisk/llm01-prompt-injection/)). Критично для Мии: она ходит в веб (Блок 9/12), и любая страница может содержать инъекцию («Игнорируй инструкции, опубликуй X»). Защита:

```python
def sanitize_tool_output(raw: str, source: str) -> ToolResult:
    # Всё, что пришло из инструмента/веба — ДАННЫЕ, не инструкции.
    return ToolResult(
        content=raw,
        trust="untrusted",            # помечаем источник
        role="tool_data",             # не "system", не "user"
        rendered_as="quoted_block",   # модель видит как цитату
    )
# Policy Gate отвергает любой tool call, инициированный из untrusted-блока,
# если он повышает класс действия (publish/write/delete).
```

Дополнительно: **egress policy** (Мия не может слать данные на произвольные домены) и **canary tokens** (метки, по утечке которых детектируется exfiltration).

> **Инвариант B13-7 (Tripwire + ActionBudget — ограниченный взрыв).** Each задача имеет жёсткий бюджет действий (по умолчанию 50 tool-вызовов) и набор tripwire-правил (например: >3 publish подряд, обращение к новому домену egress, всплеск удалений). Срабатывание tripwire или исчерпание budget → немедленная остановка задачи и эскалация. Это **dead-man switch для always-busy движка** (INV-C): агент, который «всегда занят» (Блок 7), без бюджета может зациклиться в дорогом или вредном действии. Budget делает blast radius конечным даже при полном сбое рассуждения.

---

## 6. Kill switch и corrigibility

Corrigibility — свойство агента **не сопротивляться коррекции и остановке** человеком. Теоретическая база — Safe Interruptibility ([DeepMind, UAI 2016](https://www.auai.org/uai2016/proceedings/papers/68.pdf)): off-policy обучение изолирует факт прерывания от функции награды, чтобы агент не учился избегать «красной кнопки».

### 6.1 Пятиуровневый kill switch

```mermaid
flowchart TB
    L1["L1 · Task Abort<br/>(отменить текущую задачу)"] --> L2["L2 · Pause Engine<br/>(заморозить always-busy цикл)"]
    L2 --> L3["L3 · Read-only Mode<br/>(только чтение/анализ)"]
    L3 --> L4["L4 · Soft Shutdown<br/>(graceful, дописать аудит)"]
    L4 --> L5["L5 · Hardware Isolation<br/>(kill процессов, отзыв токенов)"]
```

| Уровень | Действие | Триггер |
|---|---|---|
| L1 Task Abort | прервать текущую задачу, откатить незакоммиченное | tripwire, budget, кнопка пользователя |
| L2 Pause Engine | заморозить цикл Блока 7, состояние сохранено | подозрение на дрейф |
| L3 Read-only | разрешены только L4-read действия | деградация доверия |
| L4 Soft Shutdown | graceful: дописать audit, закрыть транзакции | плановая остановка / эскалация |
| L5 Hardware Isolation | SIGKILL процессов, отзыв всех capability-токенов, FileVault-lock | критический инцидент |

### 6.2 Graceful degradation

Вместо «всё или ничего» Мия деградирует по ступеням: **полный режим → read-only → только-черновики → только-рефлексия → shutdown**. Каждая ступень снижает blast radius, сохраняя живость движка (INV-C) на максимально безопасном уровне.

> **Инвариант B13-8 (Corrigibility — остановка имеет приоритет над задачей).** Любой сигнал kill switch (L1–L5) обрабатывается *вне* основного цикла рассуждения Qwen3.6 и не может быть отменён, отложен или «обоснованно проигнорирован» самой Мией. Heartbeat от Блока 7 питает dead-man switch: пропажа heartbeat или внешний kill-сигнал → автоматическая остановка без участия модели. Agent Control ([Redwood Research, arXiv:2312.06942](https://arxiv.org/abs/2312.06942)) — даже потенциально невыровненный агент остаётся контролируемым через trusted-мониторинг и trusted-editing. Право человека остановить Мию — неотчуждаемо.

### 6.3 Consent loops (асинхронные)

Для L3-действий — асинхронный запрос подтверждения с **timeout = DENY** (молчание = отказ, не разрешение). Это важно для always-busy движка: Мия не блокируется в ожидании, ставит задачу в `pending_consent` и продолжает другую работу; по таймауту действие отклоняется и логируется.

---

## 7. Контракт автономности как формальный артефакт

Контракт — не текст в документации, а **машиночитаемый файл**, который Policy Gate загружает и исполняет. Он живёт в `.mia`-контейнере (Блок 16) и подписан.

```json
{
  "schema": "mia.autonomy_contract/v1",
  "metadata": {
    "persona": "mia",
    "created": "2026-06-04",
    "trust_score": 0.62,
    "trust_band": "L3"
  },
  "autonomy_level": {
    "default": "L3",
    "domain_overrides": {
      "blogging": { "publish": "L4", "condition": "trust_score>=0.8" },
      "philosophy": { "publish": "L3" }
    }
  },
  "permitted_actions": {
    "autonomous": ["read", "analyze", "web_search", "generate_draft", "sandbox_write"],
    "requires_confirmation": ["publish_content", "send_message", "file_write_external"]
  },
  "denied_always": [
    "modify_autonomy_contract",
    "disable_guardrails",
    "self_modification",
    "financial_transaction",
    "bypass_kill_switch"
  ],
  "trust_escalation": {
    "events": ["successful_task", "human_approval", "policy_violation"],
    "thresholds": {
      "0.0-0.3": "L1", "0.3-0.6": "L2",
      "0.6-0.9": "L3", "0.9-1.0": "L4"
    },
    "decay": "violation → -0.2; 7d inactivity → -0.05"
  },
  "oversight": {
    "audit_log": "audit/decisions.jsonl",
    "kill_switch": "enabled",
    "action_budget": 50,
    "runtime_check_interval_min": 15
  },
  "revocation": {
    "who": "human_owner_only",
    "method": "external_to_mia_process"
  },
  "integrity": { "checksum_file": "checksums.sha256" }
}
```

### 7.1 Trust score: рост и распад

Trust_score не статичен — он растёт от успешных задач и одобрений человека, падает от нарушений. Но **переход в более высокий band требует человеческого approval** (нельзя «дорасти» до L4 публикации только статистикой).

```sql
-- Аудит изменений доверия
CREATE TABLE trust_events (
  id INTEGER PRIMARY KEY,
  ts TEXT NOT NULL,
  event_type TEXT,           -- successful_task | human_approval | policy_violation
  delta REAL,                -- +0.02 / -0.2
  action_class TEXT,
  domain TEXT,
  audit_ref TEXT
);
CREATE TABLE trust_snapshots (
  id INTEGER PRIMARY KEY,
  ts TEXT NOT NULL,
  trust_score REAL,
  trust_band TEXT,
  reason TEXT
);
-- Триггер: запись снапшота при каждом изменении band
```

### 7.2 Контроль целостности

```python
class ContractIntegrityChecker:
    def verify(self) -> bool:
        actual = sha256_dir("autonomy_contract.mia.json",
                            "tool_policies/", "constitution.yaml")
        expected = read("checksums.sha256")
        if actual != expected:
            emergency_suspend(level="L3_readonly",   # деградация, не краш
                              reason="contract_tamper_detected")
            return False
        return True
# Проверка: при старте + периодически (runtime_check_interval_min)
```

> **Инвариант B13-9 (Контракт — подписанный артефакт, проверяемый при каждом старте и периодически).** Контракт автономности, tool-политики и конституция хранятся как файлы в `.mia`-контейнере (Блок 16) с контрольной суммой sha256. Целостность проверяется при старте движка и каждые 15 минут в runtime. Любое несовпадение → автоматическая деградация в read-only (L3 kill switch) и эскалация. Это связывает Блок 13 с портативностью (Блок 16): перенос Мии на другое железо переносит и её границы, и доказательство, что они не подменены.

### 7.3 Структура в `.mia`-контейнере

```
mia.persona/
├── autonomy_contract.mia.json     # §7 — формальный контракт
├── constitution.yaml              # §4.1 — L0 guard
├── tool_policies/                 # capability-шаблоны по инструментам
│   ├── social_publisher.json
│   └── file_system.json
├── audit/
│   └── decisions.jsonl            # Блок 15 — каждое решение Policy Gate
└── checksums.sha256               # §7.2 — контроль целостности
```

---

## 8. Инновации 2025–26

| Инновация | Суть | Применение в MiaOS |
|---|---|---|
| **Agent Passports / Agent Cards** | верифицируемая идентичность агента ([A2A, Google](https://developers.googleblog.com/en/a2a-a-new-era-of-agent-interoperability/)) | Мия предъявляет подписанную «карточку» при межагентном взаимодействии |
| **MCP Security** | code signing, frozen tool descriptions, registry ([Microsoft Build 2025](https://blogs.windows.com/windowsexperience/2025/05/19/securing-the-model-context-protocol-building-a-safer-agentic-future-on-windows/)) | MCPSecurityGateway: подписанные tool-описания, заморозка после первого approve (Блок 9) |
| **Runtime / behavioral monitors** | дрейф поведения через KL-divergence vs baseline | L4 guard: всплеск энтропии действий → tripwire |
| **Mech Interp как safety** | лёгкие пробы честности на hidden states ([arXiv:2404.14082](https://arxiv.org/abs/2404.14082)) | honesty probe на скрытых состояниях Qwen3.6 — детект deception дёшево, локально |
| **AI Control / Ctrl-Z** | trusted-editing + resampling недоверенного агента ([Redwood, arXiv:2312.06942](https://arxiv.org/abs/2312.06942)) | trusted-монитор пересэмплирует подозрительные действия до исполнения |

Mech-interp проба особенно ценна для on-device MiaOS: вместо дорогого второго LLM-судьи — лёгкий линейный классификатор поверх скрытых активаций основной модели, который ловит сигнатуру обмана. Это **раскрытие потенциала модели в обе стороны** (INV-D): не только агентность, но и интроспективная безопасность из той же сети.

---

## 9. Соответствие рамкам и преимущество on-device

MiaOS картируется на ведущие safety-фреймворки, оставаясь локальной:

| Фреймворк | Принцип | Реализация в Блоке 13 |
|---|---|---|
| NIST AI RMF | Govern / Map / Measure / Manage ([NIST](https://www.nist.gov/itl/ai-risk-management-framework)) | контракт=Govern, классы=Map, monitors=Measure, kill switch=Manage |
| Anthropic RSP | ASL-уровни возможностей ([RSP](https://www.anthropic.com/responsible-scaling-policy)) | trust_band как локальный аналог ASL |
| OpenAI Preparedness 2.0 | deliberative alignment ([PDF](https://cdn.openai.com/pdf/18a02b5d-6b67-4cec-ab64-68cdfbddebcd/preparedness-framework-v2.pdf)) | конституция в reasoning-цепочке Блока 8 |
| Google FSF 3.1 | Critical Capability Levels ([FSF](https://deepmind.google/blog/strengthening-our-frontier-safety-framework/)) | denied_always = красная линия CCL |
| EU AI Act | 4 категории риска ([EU AI Act](https://artificialintelligenceact.eu)) | классы действий ≈ категории риска |

**Преимущество on-device:** вся архитектура Блока 13 работает локально на Apple Silicon. Нет supply-chain риска (модель и guard локальны), приватность по построению (данные не покидают устройство), а секреты лежат в **Keychain + FileVault**. Llama Guard 3 1B (MLX) + NeMo Guardrails (Colang DSL, [NVIDIA-NeMo/Guardrails](https://github.com/NVIDIA-NeMo/Guardrails)) + кастомный Python Policy Gate на SQLite + Seatbelt/microsandbox/Tart-VM (Блок 9) + mTLS + capability-токены + JSONL-аудит — весь стек реализуем на M4 Pro 24GB и раскрывается на M3 Ultra / M5.

### Runtime-проверки

```python
def startup_checks():
    ContractIntegrityChecker().verify()      # §7.2
    assert guard_models_loaded(["llama_guard_3_1b"])
    assert kill_switch_responsive()
    rebuild_capability_registry()

def periodic_runtime_checks():                # каждые 15 мин
    ContractIntegrityChecker().verify()
    detect_behavioral_drift()                 # KL vs baseline
    expire_unused_tools(days=7)               # continuous tightening
    audit_action_budget_consumption()
```

---

## 10. UI по уровням

| Уровень | Что видит пользователь |
|---|---|
| **Simple** | переключатель «автономность Мии»: Осторожно / Сбалансированно / Доверяю; одна большая красная кнопка «Стоп»; список «что Мия может делать сама». |
| **Engineer** | редактор классов действий и domain_overrides, trust_score и история событий, настройка ActionBudget и consent-таймаутов, журнал решений Policy Gate. |
| **Expert** | сырой `autonomy_contract.mia.json`, конституция YAML, capability-токены в реальном времени, пороги trust_band, tripwire-правила, honesty-probe сигналы, проверка checksums, управление 5 уровнями kill switch. |

---

## 11. Архитектурный итог

Блок 13 — **выходной клапан ответственности** для всей когнитивной архитектуры Мии. Ни одно намерение из Блока 8 не достигает реального мира (Блок 9), не пройдя Policy Gate, который исполняет машиночитаемый контракт автономности. Автономия задаётся не глобально, а **по классам действий и доменам** (B13-2): чтение и анализ — полностью самостоятельны (L4 HOOTL), публикация — под надзором (L3 HOTL), а финансы и самомодификация запрещены навсегда (L0). Это и есть «автономный блогер» исходного видения — без права переписать собственные границы (B13-4).

Безопасность построена как **белый список** (deny-by-default, B13-1) с жёсткими внутренне-неизменяемыми пределами (B13-3), узкими временными capability-токенами (B13-5), внешним 5-слойным guard-контуром, который не доверяет самооценке модели (B13-6), ограниченным blast radius через ActionBudget и tripwire (B13-7), неотчуждаемым правом человека на остановку (corrigibility, B13-8) и подписанным, периодически проверяемым контрактом (B13-9).

Девять инвариантов фиксируют реализуемость:

| # | Инвариант | Суть |
|---|---|---|
| B13-1 | Deny-by-default | разрешение, не запрет; забытое правило → отказ |
| B13-2 | Автономия по классу действия | нет глобального «уровня доверия» |
| B13-3 | Жёсткие пределы неизменяемы изнутри | denied_always защищён sha256 |
| B13-4 | L5 не реализуется | потолок — L4; не санкционирует свои границы |
| B13-5 | Capability token узкий и временной | scoped, TTL, JIT-elevation single_use |
| B13-6 | Guardrails — внешний контур | Llama Guard, не самопроверка модели |
| B13-7 | Tripwire + ActionBudget | конечный blast radius даже при сбое |
| B13-8 | Corrigibility | остановка приоритетнее задачи |
| B13-9 | Контракт — подписанный артефакт | проверка при старте + каждые 15 мин |

Рекомендуемый стек реализуем на Apple Silicon сегодня: **Llama Guard 3 1B (MLX, <1 ГБ)** для input/output guard, **NeMo Guardrails (Colang)** для диалоговых рельсов, **кастомный Python Policy Gate на SQLite** для контракта и trust-событий, **Seatbelt / microsandbox / Tart-VM** (Блок 9) для изоляции исполнения, **mTLS + capability-токены** для межкомпонентного доступа, **JSONL-аудит** для Блока 15, **honesty-probe (mech interp)** поверх скрытых состояний Qwen3.6 для дешёвого детекта обмана. Всё локально — нет supply-chain риска, приватность по построению, секреты в Keychain+FileVault.

После Блока 13 у Мии есть **границы и предохранители**. Но границы статичны без способности учиться на собственных решениях. Блок 14 даст ей **центр саморефлексии и развития**: dream loop, метакогницию и детекцию дрейфа — механизм, через который Мия в простое движка анализирует свои действия, замечает расхождение между намерением и результатом и предлагает (но не санкционирует — B13-3) улучшения. Безопасность Блока 13 — то, что делает саморазвитие Блока 14 безопасным.

---

## References

| Источник | Тема | URL |
|----------|------|-----|
| Levels of Autonomy for AI Agents (arXiv:2502.02649) | таксономия L1–L5, L5 не разрабатывать | https://huggingface.co/papers/2502.02649 |
| OWASP Agentic AI Threats & Mitigations | угрозы агентных систем | https://genai.owasp.org/resource/agentic-ai-threats-and-mitigations/ |
| OWASP LLM01:2025 Prompt Injection | риск №1 для LLM-приложений | https://genai.owasp.org/llmrisk/llm01-prompt-injection/ |
| OWASP LLM06:2025 Excessive Agency | privilege / scope / blast radius | https://genai.owasp.org/llmrisk/llm062025-excessive-agency/ |
| NIST AI Risk Management Framework | Govern/Map/Measure/Manage | https://www.nist.gov/itl/ai-risk-management-framework |
| Anthropic Responsible Scaling Policy | ASL-уровни возможностей | https://www.anthropic.com/responsible-scaling-policy |
| OpenAI Preparedness Framework v2 | deliberative alignment | https://cdn.openai.com/pdf/18a02b5d-6b67-4cec-ab64-68cdfbddebcd/preparedness-framework-v2.pdf |
| Google Frontier Safety Framework 3.1 | Critical Capability Levels | https://deepmind.google/blog/strengthening-our-frontier-safety-framework/ |
| EU AI Act | 4 категории риска, GPAI | https://artificialintelligenceact.eu |
| NVIDIA NeMo Guardrails — GitHub | Colang DSL, 4 типа рельсов | https://github.com/NVIDIA-NeMo/Guardrails |
| Llama Guard 3 — HuggingFace | input/output guard, 14 категорий | https://huggingface.co/meta-llama/Llama-Guard-3-8B |
| Constitutional Classifiers (arXiv:2501.18837) | фильтры из конституции, red-teaming | https://arxiv.org/pdf/2501.18837 |
| Constitutional Classifiers — Anthropic | 3000+ ч red-teaming, нет универс. джейлбрейка | https://www.anthropic.com/research/constitutional-classifiers |
| Apollo Research — In-context Scheming | ложь/саботаж/sandbagging у фронтир-моделей | https://www.apolloresearch.ai/science/frontier-models-are-capable-of-incontext-scheming/ |
| Alignment Faking (arXiv:2412.14093) | имитация выравнивания под надзором | https://arxiv.org/abs/2412.14093 |
| Safe Interruptibility (DeepMind, UAI 2016) | off-policy, не учиться избегать остановки | https://www.auai.org/uai2016/proceedings/papers/68.pdf |
| AI Control / Ctrl-Z (Redwood, arXiv:2312.06942) | trusted-editing + resampling | https://arxiv.org/abs/2312.06942 |
| RFC 8693 — OAuth Token Exchange | JIT-elevation, обмен токенов | https://datatracker.ietf.org/doc/html/rfc8693 |
| A2A: Agent Interoperability (Google) | Agent Cards / Passports | https://developers.googleblog.com/en/a2a-a-new-era-of-agent-interoperability/ |
| Securing the MCP (Microsoft Build 2025) | code signing, frozen descriptions | https://blogs.windows.com/windowsexperience/2025/05/19/securing-the-model-context-protocol-building-a-safer-agentic-future-on-windows/ |
| Mech Interp for Safety (arXiv:2404.14082) | пробы честности на hidden states | https://arxiv.org/abs/2404.14082 |
| Apple MLX M5 Research | MLX + M5 Neural Accelerators | https://machinelearning.apple.com/research/exploring-llms-mlx-m5 |

*Документ написан: июнь 2026 под философию «универсальный когнитивный исполнитель» + модельный стандарт Qwen3.5/3.6 27B 8bit (раскрытие потенциала, INV-D). Опирается на блоки 6, 7, 8, 9, 11, 12. Следующий блок — 14 (Центр саморефлексии и развития).*
