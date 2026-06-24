import { useCallback, useEffect, useRef, useState } from 'react';
import {
  addAeonGoal,
  consolidateAeon,
  deactivateAeonGoal,
  fetchAeonStatus,
  fetchProviders,
  runAeonTick,
  sendAeonMessage,
  type MiaosProviderInfo,
  type MiaosAeonGoal,
  type MiaosAeonResponse,
  type MiaosAeonStatus,
  type MiaosAeonTickResult,
} from './miaosApi';
import {
  DEFAULT_PROVIDER,
  isLocalModelProviderAvailable,
  pickDefaultProvider,
  providerDisplayName,
} from './providerPrefs';

interface AeonStudioProps {
  onTraceId?: (traceId: string) => void;
}

interface AeonMessage {
  id: string;
  role: 'user' | 'assistant' | 'system';
  text: string;
  traceId?: string;
  blocked?: boolean;
  mode?: string;
  graphId?: string | null;
}

function readableAeonText(text: string): string {
  const memoryMarker = '[AEON memory context]';
  const reasoningMarkers = ['Thinking Process:', 'Thinking process:', 'Reasoning:', 'Chain of thought:', 'Thought process:'];
  const finalMarkers = ['Final Answer:', 'Final answer:', 'Answer:', 'Ответ:'];
  const memoryIndex = text.indexOf(memoryMarker);
  const reasoningIndexes = reasoningMarkers.map((marker) => text.indexOf(marker)).filter((index) => index >= 0);
  const reasoningIndex = reasoningIndexes.length ? Math.min(...reasoningIndexes) : -1;
  const hasMarkdownArtifact = text.startsWith('**\n*') || text.startsWith('** *');

  if (memoryIndex === -1 && reasoningIndex === -1 && !hasMarkdownArtifact) return text;

  const finalMarker = finalMarkers.find((marker) => text.includes(marker));
  if (finalMarker) return text.split(finalMarker, 2)[1].trim();

  if (!hasMarkdownArtifact) {
    const markerIndex = [memoryIndex, reasoningIndex].filter((index) => index >= 0).sort((a, b) => a - b)[0];
    const visible = text.slice(0, markerIndex).trim();
    if (visible && !visible.startsWith('morning_consolidation:')) return visible;
  }
  return 'Сейчас запрос проходит проверку правил, получает контекст целей и памяти и передается в исполнительный слой.';
}

function surpriseLabel(surprise: string): string {
  if (surprise === 'low') return 'низкая неожиданность';
  if (surprise === 'medium') return 'средняя неожиданность';
  if (surprise === 'high') return 'высокая неожиданность';
  return surprise;
}

function tickActionLabel(action: string): string {
  if (action === 'routine_monitor') return 'наблюдение';
  if (action === 'local_plan') return 'локальный план';
  if (action === 'escalate_to_governance') return 'проверка правил';
  return action;
}

export function AeonStudio({ onTraceId }: AeonStudioProps) {
  const [providers, setProviders] = useState<MiaosProviderInfo[]>([]);
  const [selectedProvider, setSelectedProvider] = useState(DEFAULT_PROVIDER);
  const [forceGraph, setForceGraph] = useState(false);
  const [autoHeartbeat, setAutoHeartbeat] = useState(false);
  const [inputText, setInputText] = useState('Привет! Расскажи, как работает AEON без GCS.');
  const [goalTitle, setGoalTitle] = useState('');
  const [goalDescription, setGoalDescription] = useState('');
  const [messages, setMessages] = useState<AeonMessage[]>([]);
  const [status, setStatus] = useState<MiaosAeonStatus | null>(null);
  const [lastTick, setLastTick] = useState<MiaosAeonTickResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const tickInFlight = useRef(false);
  const providerTouched = useRef(false);

  const refreshStatus = useCallback(async () => {
    try {
      const next = await fetchAeonStatus();
      setStatus(next);
    } catch {
      setStatus(null);
    }
  }, []);

  useEffect(() => {
    void (async () => {
      try {
        const providerList = await fetchProviders();
        setProviders(providerList);
        setSelectedProvider((prev) => {
          const current = providerList.find((item) => item.name === prev);
          if (providerTouched.current && current?.available) return prev;
          return pickDefaultProvider(providerList);
        });
      } catch {
        setProviders([]);
      }
      await refreshStatus();
    })();
  }, [refreshStatus]);

  const runTick = useCallback(async () => {
    if (tickInFlight.current) return;
    tickInFlight.current = true;
    setBusy(true);
    setError(null);
    try {
      const tick = await runAeonTick();
      setLastTick(tick);
      setMessages((prev) => [
        ...prev,
        {
          id: `tick-${tick.tick_id}`,
          role: 'system',
          text: `Цикл обновлён: ${surpriseLabel(tick.surprise)}, оценка ${tick.surprise_score.toFixed(2)}, действие — ${tickActionLabel(tick.action)}.`,
        },
      ]);
      await refreshStatus();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Не удалось выполнить heartbeat');
    } finally {
      tickInFlight.current = false;
      setBusy(false);
    }
  }, [refreshStatus]);

  useEffect(() => {
    if (!autoHeartbeat || !status?.heartbeat_interval_seconds) return undefined;
    const intervalMs = status.heartbeat_interval_seconds * 1000;
    const timer = window.setInterval(() => {
      void runTick();
    }, intervalMs);
    return () => window.clearInterval(timer);
  }, [autoHeartbeat, runTick, status?.heartbeat_interval_seconds]);

  const sendMessage = useCallback(async () => {
    const text = inputText.trim();
    if (!text) return;

    setBusy(true);
    setError(null);
    setMessages((prev) => [...prev, { id: `u-${Date.now()}`, role: 'user', text }]);
    setInputText('');

    try {
      const response: MiaosAeonResponse = await sendAeonMessage(text, {
        provider: selectedProvider,
        forceGraph,
      });
      onTraceId?.(response.trace_id);
      setMessages((prev) => [
        ...prev,
        {
          id: `a-${response.trace_id}`,
          role: 'assistant',
          text: response.text,
          traceId: response.trace_id,
          blocked: response.blocked,
          mode: response.execution_mode,
          graphId: response.graph_id,
        },
      ]);
      await refreshStatus();
      window.dispatchEvent(new CustomEvent('miya:studio-refresh'));
      window.dispatchEvent(new CustomEvent('miya:aeon-ask', { detail: { traceId: response.trace_id } }));
      sessionStorage.setItem('miya:aeon-responded', '1');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Не удалось отправить запрос в AEON');
    } finally {
      setBusy(false);
    }
  }, [forceGraph, inputText, onTraceId, refreshStatus, selectedProvider]);

  const submitGoal = useCallback(async () => {
    const title = goalTitle.trim();
    const description = goalDescription.trim();
    if (!title || !description) return;

    setBusy(true);
    setError(null);
    try {
      await addAeonGoal(title, description, { provider: selectedProvider });
      setGoalTitle('');
      setGoalDescription('');
      await refreshStatus();
      window.dispatchEvent(new CustomEvent('miya:aeon-goal-added'));
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Не удалось добавить цель');
    } finally {
      setBusy(false);
    }
  }, [goalDescription, goalTitle, refreshStatus, selectedProvider]);

  const deactivateGoal = useCallback(
    async (goalId: string) => {
      setBusy(true);
      setError(null);
      try {
        await deactivateAeonGoal(goalId);
        await refreshStatus();
        window.dispatchEvent(new CustomEvent('miya:studio-refresh'));
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Не удалось деактивировать цель');
      } finally {
        setBusy(false);
      }
    },
    [refreshStatus],
  );

  const runConsolidation = useCallback(async () => {
    setBusy(true);
    setError(null);
    try {
      const result = await consolidateAeon();
      setMessages((prev) => [
        ...prev,
        {
          id: `consolidate-${Date.now()}`,
          role: 'system',
          text: `Память обновлена: активных целей ${result.active_goal_count}, обработано эпизодов ${result.episodes_seen}.`,
        },
      ]);
      await refreshStatus();
      window.dispatchEvent(new CustomEvent('miya:aeon-consolidated'));
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Не удалось закрепить память');
    } finally {
      setBusy(false);
    }
  }, [refreshStatus]);

  const activeGoals = status?.active_goals ?? [];

  return (
    <section id="miya-aeon-studio" className="miya-aeon-studio">
      <div className="miya-run-header">
        <h2 className="miya-run-title">AEON</h2>
        <span className="miya-run-badge">{status?.identity || 'AEON'}</span>
        {status && (
          <span className={`miya-run-badge ${status.available ? 'miya-run-badge-ok' : 'miya-run-badge-off'}`}>
            {status.available ? 'готов' : 'недоступен'}
          </span>
        )}
      </div>

      <p className="miya-run-hint">
        AEON держит в фокусе правила, цели и память. Цели и ритм обновления сохраняются между запросами.
      </p>

      <div className="miya-aeon-flow" aria-label="AEON рабочий поток">
        <div className="miya-aeon-flow-step">
          <span className="miya-aeon-flow-number">1</span>
          <strong>Спросить</strong>
          <p>Получите короткий ответ рядом с вопросом.</p>
        </div>
        <div className="miya-aeon-flow-step">
          <span className="miya-aeon-flow-number">2</span>
          <strong>Добавить цель</strong>
          <p>Зафиксируй, что Мия должна помнить.</p>
        </div>
        <div className="miya-aeon-flow-step">
          <span className="miya-aeon-flow-number">3</span>
          <strong>Закрепить память</strong>
          <p>Соберите недавние эпизоды в заметки.</p>
        </div>
      </div>

      <div className="miya-aeon-primary-ask">
        <label className="miya-field miya-chat-input">
          <span>Что спросить у AEON</span>
          <textarea
            rows={3}
            value={inputText}
            onChange={(e) => setInputText(e.target.value)}
            disabled={busy}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) {
                e.preventDefault();
                void sendMessage();
              }
            }}
          />
        </label>
        <div className="miya-run-actions">
          <button
            type="button"
            className="miya-btn miya-btn-primary"
            onClick={() => void sendMessage()}
            disabled={busy || !inputText.trim()}
          >
            {busy ? 'AEON думает…' : 'Спросить AEON'}
          </button>
          <button type="button" className="miya-btn" onClick={() => void runConsolidation()} disabled={busy}>
            Закрепить память
          </button>
        </div>
      </div>

      {messages.length > 0 && (
        <ol className="miya-chat-log miya-aeon-chat-log">
          {messages.map((message) => (
            <li
              key={message.id}
              className={`miya-chat-msg miya-chat-msg-${message.role}${message.blocked ? ' miya-chat-msg-blocked' : ''}`}
            >
              <span className="miya-chat-msg-label">
                {message.role === 'user' ? 'Вы' : 'AEON'}
              </span>
              <p className="miya-chat-msg-text">{readableAeonText(message.text)}</p>
            </li>
          ))}
        </ol>
      )}

      {status && (
        <details className="miya-advanced-section miya-aeon-runtime-details">
          <summary>
            Подробности работы: {status.active_goals.length} целей · {status.recent_ticks?.length ?? 0} циклов
          </summary>
          <div className="miya-advanced-section-body">
            <div className="miya-aeon-status-grid">
              <div className="miya-aeon-status-card">
                <span className="miya-aeon-status-label">Идентичность</span>
                <strong>{status.identity}</strong>
                <p className="miya-aeon-status-meta">модель: {status.provider}</p>
              </div>
              <div className="miya-aeon-status-card">
                <span className="miya-aeon-status-label">Ценности</span>
                <p className="miya-aeon-status-meta">{status.values.join(', ')}</p>
              </div>
              <div className="miya-aeon-status-card">
                <span className="miya-aeon-status-label">Активные цели ({status.active_goals.length})</span>
                <ul className="miya-aeon-goals">
                  {status.active_goals.map((goal: MiaosAeonGoal) => (
                    <li key={goal.id} className="miya-aeon-goal-item">
                      <div className="miya-aeon-goal-head">
                        <strong>{goal.title}</strong>
                        <span className="miya-aeon-status-meta">
                          p={goal.priority.toFixed(2)} · {goal.source}
                        </span>
                      </div>
                      <div className="miya-aeon-progress" aria-label={`progress ${goal.progress}`}>
                        <span style={{ width: `${Math.round(goal.progress * 100)}%` }} />
                      </div>
                      {goal.source !== 'seed' && (
                        <button
                          type="button"
                          className="miya-btn miya-btn-secondary miya-aeon-goal-deactivate"
                          onClick={() => void deactivateGoal(goal.id)}
                          disabled={busy}
                        >
                          Деактивировать
                        </button>
                      )}
                    </li>
                  ))}
                </ul>
              </div>
              {status.recent_ticks && status.recent_ticks.length > 0 && (
                <div className="miya-aeon-status-card">
                  <span className="miya-aeon-status-label">Последние циклы</span>
                  <ul className="miya-aeon-goals">
                    {status.recent_ticks.map((tick) => (
                      <li key={tick.tick_id}>
                        {tick.tick_id} · {surpriseLabel(tick.surprise)} · {tickActionLabel(tick.action)}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          </div>
        </details>
      )}

      <div className="miya-aeon-goal-form">
        <label className="miya-field">
          <span>Новая цель — заголовок</span>
          <input
            value={goalTitle}
            onChange={(e) => setGoalTitle(e.target.value)}
            placeholder="Помогать с архитектурой проекта"
            disabled={busy}
          />
        </label>
        <label className="miya-field">
          <span>Описание цели</span>
          <input
            value={goalDescription}
            onChange={(e) => setGoalDescription(e.target.value)}
            placeholder="Держать в фокусе текущий репозиторий и документировать решения"
            disabled={busy}
          />
        </label>
        <button type="button" className="miya-btn miya-btn-secondary" onClick={() => void submitGoal()} disabled={busy}>
          Добавить цель
        </button>
      </div>

      <section className="miya-aeon-saved-goals" aria-label="Сохранённые цели AEON">
        <div className="miya-aeon-saved-goals-head">
          <div>
            <h3>Сохранённые цели</h3>
            <p>
              Хранятся в <code>MIYA_DATA_DIR/aeon_goals.json</code>. По умолчанию:{' '}
              <code>~/Documents/miya/.miaos/aeon_goals.json</code>.
            </p>
          </div>
          <button
            type="button"
            className="miya-btn miya-btn-secondary"
            onClick={() => void refreshStatus()}
            disabled={busy}
          >
            Обновить
          </button>
        </div>
        {activeGoals.length > 0 ? (
          <ul className="miya-aeon-goals miya-aeon-saved-goals-list">
            {activeGoals.map((goal: MiaosAeonGoal) => (
              <li key={goal.id} className="miya-aeon-goal-item">
                <div className="miya-aeon-goal-head">
                  <strong>{goal.title}</strong>
                  <span className="miya-aeon-status-meta">
                    {goal.source} · p={goal.priority.toFixed(2)}
                  </span>
                </div>
                <p className="miya-aeon-status-meta">{goal.description}</p>
                <div className="miya-aeon-progress" aria-label={`progress ${goal.progress}`}>
                  <span style={{ width: `${Math.round(goal.progress * 100)}%` }} />
                </div>
                {goal.source !== 'seed' && (
                  <button
                    type="button"
                    className="miya-btn miya-btn-secondary miya-aeon-goal-deactivate"
                    onClick={() => void deactivateGoal(goal.id)}
                    disabled={busy}
                  >
                    Деактивировать
                  </button>
                )}
              </li>
            ))}
          </ul>
        ) : (
          <p className="miya-run-hint">Пока активных целей нет или статус AEON ещё не загружен.</p>
        )}
      </section>

      <details className="miya-advanced-section">
        <summary>Дополнительные настройки</summary>
        <div className="miya-advanced-section-body">
          <div className="miya-chat-controls">
            <label className="miya-field">
              <span>Провайдер</span>
              <select
                value={selectedProvider}
                onChange={(e) => {
                  providerTouched.current = true;
                  setSelectedProvider(e.target.value);
                }}
                disabled={busy}
              >
                {(providers.length ? providers : [{ name: 'mock', available: true, description: '' }]).map(
                  (item) => (
                    <option key={item.name} value={item.name} disabled={!item.available}>
                      {providerDisplayName(item.name)}
                      {item.available ? '' : ' (недоступен)'}
                    </option>
                  ),
                )}
              </select>
            </label>

            <label className="miya-field miya-aeon-checkbox">
              <span>Всегда запускать граф</span>
              <input
                type="checkbox"
                checked={forceGraph}
                onChange={(e) => setForceGraph(e.target.checked)}
                disabled={busy}
              />
            </label>

            <label className="miya-field miya-aeon-checkbox">
              <span>Автообновление</span>
              <input
                type="checkbox"
                checked={autoHeartbeat}
                onChange={(e) => setAutoHeartbeat(e.target.checked)}
                disabled={busy}
              />
            </label>
          </div>

          <div className="miya-run-actions">
            <button type="button" className="miya-btn" onClick={() => void runTick()} disabled={busy}>
              Обновить цикл
            </button>
            <button
              type="button"
              className="miya-btn miya-btn-secondary"
              onClick={() => void refreshStatus()}
              disabled={busy}
            >
              Обновить статус
            </button>
          </div>

          {providers.length > 0 && !isLocalModelProviderAvailable(providers) && (
            <p className="miya-run-hint">
              Для прямого MLX перезапустите backend:{' '}
              <code>MIYA_WITH_MLX=1 ~/Documents/miya/frontend/scripts/start-miaos-backend.sh</code>
            </p>
          )}

          {lastTick && (
            <p className="miya-run-hint">
              Последний heartbeat: {lastTick.tick_id} · governance_ok={String(lastTick.governance_ok)}
            </p>
          )}
        </div>
      </details>

      {error && <pre className="miya-run-error">{error}</pre>}
    </section>
  );
}
