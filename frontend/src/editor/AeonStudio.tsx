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
import { DEFAULT_PROVIDER, isMlxAvailable, pickDefaultProvider } from './providerPrefs';

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
          if (current?.available) return prev;
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
          text: `Heartbeat: surprise=${tick.surprise} (${tick.surprise_score.toFixed(2)}), action=${tick.action}`,
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
          text: `Consolidation: retired=${result.retired_goal_ids.length}, active=${result.active_goal_count}, episodes=${result.episodes_seen}`,
        },
      ]);
      await refreshStatus();
      window.dispatchEvent(new CustomEvent('miya:aeon-consolidated'));
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Не удалось выполнить consolidation');
    } finally {
      setBusy(false);
    }
  }, [refreshStatus]);

  const activeGoals = status?.active_goals ?? [];

  return (
    <section id="miya-aeon-studio" className="miya-aeon-studio">
      <div className="miya-run-header">
        <h2 className="miya-run-title">AEON Studio</h2>
        <span className="miya-run-badge">{status?.identity || 'AEON'}</span>
        {status && (
          <span className={`miya-run-badge ${status.available ? 'miya-run-badge-ok' : 'miya-run-badge-off'}`}>
            {status.available ? 'online' : 'offline'}
          </span>
        )}
      </div>

      <p className="miya-run-hint">
        AEON без GCS: constitution → governance → goals → memory → fixed MiaOS execution. Цели и heartbeat
        сохраняются между запросами.
      </p>

      <div className="miya-aeon-flow" aria-label="AEON рабочий поток">
        <div className="miya-aeon-flow-step">
          <span className="miya-aeon-flow-number">1</span>
          <strong>Спросить</strong>
          <p>Проверь ответ AEON и trace.</p>
        </div>
        <div className="miya-aeon-flow-step">
          <span className="miya-aeon-flow-number">2</span>
          <strong>Добавить цель</strong>
          <p>Зафиксируй, что Мия должна помнить.</p>
        </div>
        <div className="miya-aeon-flow-step">
          <span className="miya-aeon-flow-number">3</span>
          <strong>Consolidation</strong>
          <p>Сожми эпизоды в skill notes.</p>
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
            Consolidation
          </button>
        </div>
      </div>

      {status && (
        <details className="miya-advanced-section miya-aeon-runtime-details">
          <summary>
            Runtime details: {status.active_goals.length} goals · {status.recent_ticks?.length ?? 0} ticks
          </summary>
          <div className="miya-advanced-section-body">
            <div className="miya-aeon-status-grid">
              <div className="miya-aeon-status-card">
                <span className="miya-aeon-status-label">Identity</span>
                <strong>{status.identity}</strong>
                <p className="miya-aeon-status-meta">provider: {status.provider}</p>
              </div>
              <div className="miya-aeon-status-card">
                <span className="miya-aeon-status-label">Values</span>
                <p className="miya-aeon-status-meta">{status.values.join(', ')}</p>
              </div>
              <div className="miya-aeon-status-card">
                <span className="miya-aeon-status-label">Active goals ({status.active_goals.length})</span>
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
                  <span className="miya-aeon-status-label">Recent heartbeats</span>
                  <ul className="miya-aeon-goals">
                    {status.recent_ticks.map((tick) => (
                      <li key={tick.tick_id}>
                        {tick.tick_id} · {tick.surprise} · {tick.action}
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
        <summary>Advanced controls</summary>
        <div className="miya-advanced-section-body">
          <div className="miya-chat-controls">
            <label className="miya-field">
              <span>Провайдер</span>
              <select
                value={selectedProvider}
                onChange={(e) => setSelectedProvider(e.target.value)}
                disabled={busy}
              >
                {(providers.length ? providers : [{ name: 'mock', available: true, description: '' }]).map(
                  (item) => (
                    <option key={item.name} value={item.name} disabled={!item.available}>
                      {item.name}
                      {item.available ? '' : ' (недоступен)'}
                    </option>
                  ),
                )}
              </select>
            </label>

            <label className="miya-field miya-aeon-checkbox">
              <span>Force graph</span>
              <input
                type="checkbox"
                checked={forceGraph}
                onChange={(e) => setForceGraph(e.target.checked)}
                disabled={busy}
              />
            </label>

            <label className="miya-field miya-aeon-checkbox">
              <span>Auto heartbeat</span>
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
              Heartbeat tick
            </button>
            <button
              type="button"
              className="miya-btn miya-btn-secondary"
              onClick={() => void refreshStatus()}
              disabled={busy}
            >
              Обновить status
            </button>
          </div>

          {providers.length > 0 && !isMlxAvailable(providers) && (
            <p className="miya-run-hint">
              Для локальной генерации перезапустите backend:{' '}
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

      {messages.length > 0 && (
        <ol className="miya-chat-log">
          {messages.map((message) => (
            <li
              key={message.id}
              className={`miya-chat-msg miya-chat-msg-${message.role}${message.blocked ? ' miya-chat-msg-blocked' : ''}`}
            >
              <span className="miya-chat-msg-label">
                {message.role === 'user' ? 'Вы' : message.role === 'system' ? 'AEON system' : 'AEON'}
                {message.traceId ? ` · ${message.traceId}` : ''}
                {message.mode ? ` · ${message.mode}` : ''}
                {message.graphId ? ` · ${message.graphId}` : ''}
              </span>
              <p className="miya-chat-msg-text">{message.text}</p>
            </li>
          ))}
        </ol>
      )}

      {error && <pre className="miya-run-error">{error}</pre>}
    </section>
  );
}
