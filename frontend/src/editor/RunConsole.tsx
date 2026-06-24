import { useCallback, useEffect, useRef, useState } from 'react';
import type { Graph } from '@antv/x6';
import {
  checkMiaosHealth,
  fetchProviders,
  runMiaosGraph,
  validateMiaosGraphRemote,
  watchRunEvents,
  type MiaosGraphEvent,
  type MiaosGraphRun,
  type MiaosProviderInfo,
} from './miaosApi';
import { buildMiaosNodeIdMap, exportToMiaosGraph } from './miaosExport';
import { applyRunEvent, delay, resetRunVisuals } from './runHighlight';
import { applyEventsUpTo, replayGraphEvents } from './runReplay';
import { extractMiaAnswer, extractMiaQuestion } from './runOutput';
import {
  DEFAULT_PROVIDER,
  isLocalModelProviderAvailable,
  pickDefaultProvider,
  providerDescription,
  providerDisplayName,
} from './providerPrefs';
import { setStatus } from '../miyaBridge';

interface RunConsoleProps {
  graph: Graph | null;
  syncedRun?: MiaosGraphRun | null;
  onRunComplete?: (run: MiaosGraphRun) => void;
}

const EVENT_STEP_MS = 400;
const REPLAY_SPEEDS = [
  { label: 'Быстро', ms: 200 },
  { label: 'Норма', ms: 400 },
  { label: 'Медленно', ms: 800 },
] as const;

export function RunConsole({ graph, syncedRun, onRunComplete }: RunConsoleProps) {
  const [online, setOnline] = useState<boolean | null>(null);
  const [inputText, setInputText] = useState('Привет, Mia! Спланируй короткий ответ.');
  const [busy, setBusy] = useState(false);
  const [events, setEvents] = useState<MiaosGraphEvent[]>([]);
  const [lastRun, setLastRun] = useState<MiaosGraphRun | null>(null);
  const [activeNodeId, setActiveNodeId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [checkingHealth, setCheckingHealth] = useState(false);
  const [providers, setProviders] = useState<MiaosProviderInfo[]>([]);
  const [selectedProvider, setSelectedProvider] = useState(DEFAULT_PROVIDER);
  const [replaying, setReplaying] = useState(false);
  const [replayStepMs, setReplayStepMs] = useState(EVENT_STEP_MS);
  const [replayCursor, setReplayCursor] = useState(0);
  const replayAbortRef = useRef<AbortController | null>(null);

  const refreshHealth = useCallback(async () => {
    setCheckingHealth(true);
    try {
      const ok = await checkMiaosHealth();
      setOnline(ok);
      if (ok) {
        const list = await fetchProviders();
        setProviders(list);
        setSelectedProvider((prev) => {
          const current = list.find((item) => item.name === prev);
          if (current?.available) return prev;
          return pickDefaultProvider(list);
        });
      }
      setStatus(ok ? 'MiaOS доступен' : 'MiaOS недоступен — см. запуск графа');
    } catch {
      setOnline(false);
      setStatus('MiaOS недоступен — см. запуск графа');
    } finally {
      setCheckingHealth(false);
    }
  }, []);

  useEffect(() => {
    void refreshHealth();
  }, [refreshHealth]);

  useEffect(() => {
    if (!syncedRun) return;
    setLastRun(syncedRun);
    setEvents(syncedRun.events);
    setReplayCursor(Math.max(0, syncedRun.events.length - 1));
    setActiveNodeId(null);
    setStatus(`Запуск ${syncedRun.status}: ${syncedRun.run_id}`);
  }, [syncedRun]);

  const stopReplay = useCallback(() => {
    replayAbortRef.current?.abort();
    replayAbortRef.current = null;
    setReplaying(false);
  }, []);

  const scrubReplay = useCallback(
    (targetEvents: MiaosGraphEvent[], index: number) => {
      if (!graph || targetEvents.length === 0) return;
      stopReplay();
      const safeIndex = Math.max(0, Math.min(index, targetEvents.length - 1));
      setEvents(targetEvents);
      setReplayCursor(safeIndex);
      setActiveNodeId(applyEventsUpTo(graph, targetEvents, safeIndex));
    },
    [graph, stopReplay],
  );

  const handleReplay = useCallback(
    async (targetEvents?: MiaosGraphEvent[], startIndex = 0) => {
      if (!graph) {
        window.alert('Подождите — холст ещё загружается.');
        return;
      }

      const replayEvents = targetEvents ?? events;
      if (replayEvents.length === 0) {
        window.alert('Нет событий для повтора — сначала запустите граф.');
        return;
      }

      stopReplay();
      setReplaying(true);
      setError(null);
      const controller = new AbortController();
      replayAbortRef.current = controller;

      try {
        await replayGraphEvents(graph, replayEvents, {
          stepMs: replayStepMs,
          startIndex,
          onProgress: ({ index, activeNodeId }) => {
            setReplayCursor(index);
            setActiveNodeId(activeNodeId);
          },
          signal: controller.signal,
        });
        setStatus(`Повтор завершён: ${replayEvents.length} событий`);
      } catch (err) {
        if (err instanceof DOMException && err.name === 'AbortError') {
          setStatus('Повтор остановлен');
        } else {
          const message = err instanceof Error ? err.message : 'Не удалось воспроизвести события.';
          setError(message);
          setStatus('Ошибка повтора');
        }
      } finally {
        replayAbortRef.current = null;
        setReplaying(false);
      }
    },
    [events, graph, replayStepMs, stopReplay],
  );

  const handleRun = useCallback(async () => {
    if (!graph) {
      window.alert('Подождите — холст ещё загружается.');
      return;
    }

    setBusy(true);
    setError(null);
    setEvents([]);
    setLastRun(null);
    setActiveNodeId(null);

    const idMap = buildMiaosNodeIdMap(graph);
    resetRunVisuals(idMap);

    try {
      const healthy = await checkMiaosHealth();
      setOnline(healthy);
      if (!healthy) {
        throw new Error(
          [
            'Backend MiaOS недоступен на http://127.0.0.1:8000',
            '',
            '1) Установите uv (если ещё нет):',
            '   curl -LsSf https://astral.sh/uv/install.sh | sh',
            '',
            '2) Запустите backend в отдельном терминале:',
            '   ~/Documents/miya/frontend/scripts/start-miaos-backend.sh',
            '',
            'Редактор уже может быть открыт на http://localhost:5173 —',
            'не запускайте pnpm dev повторно, если порт занят.',
          ].join('\n'),
        );
      }

      const { spec } = exportToMiaosGraph(graph);
      await validateMiaosGraphRemote(spec);
      const run = await runMiaosGraph(spec, inputText.trim() || 'test', selectedProvider);
      setLastRun(run);
      setEvents(run.events);
      setReplayCursor(Math.max(0, run.events.length - 1));
      setStatus(`WebSocket: ${run.run_id}`);

      await watchRunEvents(run.run_id, async (event) => {
        const active = applyRunEvent(idMap, event);
        setActiveNodeId(active);
        setEvents((prev) => [...prev, event]);
        await delay(EVENT_STEP_MS);
      });

      setActiveNodeId(null);
      setStatus(`Запуск ${run.status}: ${run.run_id}`);
      onRunComplete?.(run);
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Не удалось запустить граф.';
      setError(message);
      setActiveNodeId(null);
      resetRunVisuals(idMap);
      setStatus('Ошибка запуска графа');
    } finally {
      setBusy(false);
    }
  }, [graph, inputText, onRunComplete, selectedProvider]);

  useEffect(() => {
    const onRunRequest = () => {
      void handleRun();
    };
    const onReplayRun = (event: Event) => {
      const detail = (event as CustomEvent<{ events: MiaosGraphEvent[] }>).detail;
      if (detail?.events?.length) {
        setEvents(detail.events);
        void handleReplay(detail.events);
      }
    };
    const onReplayScrub = (event: Event) => {
      const detail = (event as CustomEvent<{ events: MiaosGraphEvent[]; index: number }>).detail;
      if (detail?.events?.length) {
        scrubReplay(detail.events, detail.index);
      }
    };
    window.addEventListener('miya:run-request', onRunRequest);
    window.addEventListener('miya:replay-run', onReplayRun as EventListener);
    window.addEventListener('miya:replay-scrub', onReplayScrub as EventListener);
    return () => {
      window.removeEventListener('miya:run-request', onRunRequest);
      window.removeEventListener('miya:replay-run', onReplayRun as EventListener);
      window.removeEventListener('miya:replay-scrub', onReplayScrub as EventListener);
    };
  }, [handleReplay, handleRun, scrubReplay]);

  useEffect(() => () => stopReplay(), [stopReplay]);

  const questionText = lastRun
    ? extractMiaQuestion(lastRun.outputs, inputText)
    : null;
  const answerView = lastRun ? extractMiaAnswer(lastRun.outputs, lastRun.status) : null;

  return (
    <section id="miya-run-console" className="miya-run-console">
      <div className="miya-run-header">
        <h2 className="miya-run-title">Запуск графа</h2>
        <span
          className={`miya-run-badge ${online ? 'miya-run-badge-ok' : online === false ? 'miya-run-badge-off' : ''}`}
        >
          {online === null ? 'Проверка MiaOS…' : online ? 'MiaOS доступен' : 'MiaOS недоступен'}
        </span>
        <button
          type="button"
          className="miya-btn miya-btn-secondary"
          onClick={() => void refreshHealth()}
          disabled={checkingHealth}
        >
          {checkingHealth ? 'Проверка…' : 'Проверить'}
        </button>
      </div>

      <label className="miya-field miya-run-input">
        <span>Входной запрос</span>
        <textarea
          rows={2}
          value={inputText}
          onChange={(e) => setInputText(e.target.value)}
          placeholder="Текст для узла Старт…"
          disabled={busy}
        />
      </label>

      <div className="miya-run-actions">
        <button type="button" className="miya-btn miya-btn-primary" onClick={() => void handleRun()} disabled={busy}>
          {busy ? 'Выполнение…' : 'Запустить граф'}
        </button>
      </div>

      <details className="miya-advanced-section">
        <summary>Настройки запуска</summary>
        <div className="miya-advanced-section-body">
          <label className="miya-field miya-run-input">
            <span>Провайдер модели</span>
            <select
              value={selectedProvider}
              onChange={(e) => setSelectedProvider(e.target.value)}
              disabled={busy || providers.length === 0}
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

          {providers.length > 0 && !isLocalModelProviderAvailable(providers) && (
            <p className="miya-run-provider-hint">
              Прямой MLX недоступен. Если он нужен, перезапустите backend:{' '}
              <code>MIYA_WITH_MLX=1 ~/Documents/miya/frontend/scripts/start-miaos-backend.sh</code>
            </p>
          )}

          {providers.length > 0 && (
            <p className="miya-run-provider-hint">
              {providerDescription(providers.find((item) => item.name === selectedProvider))}
            </p>
          )}
        </div>
      </details>

      {busy && activeNodeId && (
        <p className="miya-run-active">
          Активный узел: <strong>{activeNodeId}</strong>
        </p>
      )}

      {error && <pre className="miya-run-error">{error}</pre>}

      {lastRun && (
        <div className="miya-run-summary">
          <strong>Статус:</strong> {lastRun.status} · <strong>провайдер:</strong>{' '}
          {lastRun.provider || selectedProvider} · <strong>запуск:</strong> {lastRun.run_id}
          <br />
          <strong>trace_id:</strong> <code>{lastRun.trace_id}</code>
        </div>
      )}

      {lastRun && questionText && (
        <div className="miya-run-qa">
          <div className="miya-run-qa-block miya-run-qa-question">
            <span className="miya-run-qa-label">Ваш вопрос</span>
            <p className="miya-run-qa-text">{questionText}</p>
          </div>
          <div className="miya-run-qa-block miya-run-qa-answer">
            <span className="miya-run-qa-label">Ответ Мии</span>
            {answerView?.hint && <p className="miya-run-qa-hint">{answerView.hint}</p>}
            {answerView?.text ? (
              <p className="miya-run-qa-text">{answerView.text}</p>
            ) : (
              <p className="miya-run-qa-text miya-run-qa-muted">
                Пока нет — дождитесь завершения графа или одобрите согласование.
              </p>
            )}
          </div>
        </div>
      )}

      {events.length > 0 && (
        <div className="miya-replay-controls">
          <div className="miya-replay-header">
            <span className="miya-run-badge">{events.length} событий</span>
            <label className="miya-replay-speed">
              <span>Скорость</span>
              <select
                value={replayStepMs}
                onChange={(e) => setReplayStepMs(Number(e.target.value))}
                disabled={busy || replaying}
              >
                {REPLAY_SPEEDS.map((item) => (
                  <option key={item.ms} value={item.ms}>
                    {item.label}
                  </option>
                ))}
              </select>
            </label>
            <button
              type="button"
              className="miya-btn miya-btn-secondary"
              onClick={() => void handleReplay()}
              disabled={busy || replaying || !graph}
            >
              {replaying ? 'Повтор…' : 'Повторить'}
            </button>
            <button
              type="button"
              className="miya-btn"
              onClick={stopReplay}
              disabled={!replaying}
            >
              Стоп
            </button>
          </div>
          <label className="miya-replay-scrub">
            <span>
              Шаг {replayCursor + 1} / {events.length}
              {events[replayCursor]?.node_id ? ` · ${events[replayCursor].node_id}` : ''}
            </span>
            <input
              type="range"
              min={0}
              max={Math.max(0, events.length - 1)}
              value={replayCursor}
              disabled={busy || replaying || !graph}
              onChange={(e) => scrubReplay(events, Number(e.target.value))}
            />
          </label>
        </div>
      )}

      {(events.length > 0 || (lastRun && Object.keys(lastRun.outputs).length > 0)) && (
        <details className="miya-run-outputs">
          <summary>Подробности запуска: {events.length} событий и выводы узлов</summary>
          {lastRun && Object.keys(lastRun.outputs).length > 0 && (
            <>
              <h3 className="miya-run-details-title">Выводы узлов</h3>
              <pre>{JSON.stringify(lastRun.outputs, null, 2)}</pre>
            </>
          )}
          {events.length > 0 && (
            <>
              <h3 className="miya-run-details-title">Журнал событий</h3>
              <ol className="miya-run-events">
                {events.map((event, index) => (
                  <li
                    key={`${event.event_type}-${event.node_id ?? 'none'}-${index}`}
                    className={
                      index === replayCursor || event.node_id === activeNodeId
                        ? 'miya-run-event-active'
                        : undefined
                    }
                  >
                    <code>{event.event_type}</code>
                    {event.node_id ? ` · ${event.node_id}` : ''} — {event.message}
                  </li>
                ))}
              </ol>
            </>
          )}
        </details>
      )}

      {online === false && (
        <p className="miya-run-hint">
          Backend (отдельный терминал):{' '}
          <code>~/Documents/miya/frontend/scripts/start-miaos-backend.sh</code>
          <br />
          Если нет uv:{' '}
          <code>curl -LsSf https://astral.sh/uv/install.sh | sh</code>
          <br />
          Редактор: откройте <code>http://localhost:5173</code> — не нужен второй{' '}
          <code>pnpm dev</code>, если порт уже занят.
        </p>
      )}
    </section>
  );
}
