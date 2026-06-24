import { useCallback, useEffect, useMemo, useState } from 'react';
import { fetchTrace, type MiaosGraphEvent, type MiaosGraphRun, type MiaosTraceEvent } from './miaosApi';
import {
  buildPolicyRows,
  buildTraceTimeline,
  formatTraceTime,
  policyOutcomeClass,
} from './traceTimeline';

interface TraceViewerProps {
  traceId: string | null;
  run?: MiaosGraphRun | null;
}

export function TraceViewer({ traceId, run }: TraceViewerProps) {
  const [auditEvents, setAuditEvents] = useState<MiaosTraceEvent[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadTrace = useCallback(async (id: string) => {
    setLoading(true);
    setError(null);
    try {
      const trace = await fetchTrace(id);
      setAuditEvents(trace.events);
    } catch (err) {
      setAuditEvents([]);
      setError(err instanceof Error ? err.message : 'Не удалось загрузить trace');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (traceId) {
      void loadTrace(traceId);
    } else {
      setAuditEvents([]);
      setError(null);
    }
  }, [traceId, loadTrace]);

  const runEvents = useMemo<MiaosGraphEvent[]>(
    () => (run?.trace_id === traceId ? run.events : []),
    [run, traceId],
  );
  const timeline = useMemo(
    () => buildTraceTimeline(auditEvents, runEvents),
    [auditEvents, runEvents],
  );
  const policyRows = useMemo(() => buildPolicyRows(auditEvents), [auditEvents]);

  const replayOnCanvas = () => {
    if (runEvents.length === 0) return;
    window.dispatchEvent(
      new CustomEvent('miya:navigate', { detail: { tab: 'graph', target: 'miya-run-console' } }),
    );
    window.setTimeout(() => {
      window.dispatchEvent(
        new CustomEvent('miya:replay-run', { detail: { events: runEvents } }),
      );
    }, 120);
  };

  const scrubRunEvent = (itemId: string) => {
    const index = runEvents.findIndex(
      (event, eventIndex) => itemId === `run-${event.run_id}-${event.event_type}-${eventIndex}`,
    );
    if (index < 0) return;
    window.dispatchEvent(
      new CustomEvent('miya:navigate', { detail: { tab: 'graph', target: 'miya-run-console' } }),
    );
    window.setTimeout(() => {
      window.dispatchEvent(
        new CustomEvent('miya:replay-scrub', { detail: { events: runEvents, index } }),
      );
    }, 120);
  };

  return (
    <section id="miya-trace-viewer" className="miya-trace-viewer">
      <div className="miya-run-header">
        <h2 className="miya-run-title">Диагностика</h2>
        {traceId && (
          <button
            type="button"
            className="miya-btn miya-btn-secondary"
            onClick={() => void loadTrace(traceId)}
            disabled={loading || !traceId}
          >
            {loading ? 'Загрузка…' : 'Обновить'}
          </button>
        )}
      </div>

      {!traceId && (
        <p className="miya-run-hint">
          Запустите граф или отправьте сообщение в чате — здесь появятся технические детали
          выполнения и решений безопасности.
        </p>
      )}

      {traceId && (
        <p className="miya-trace-id">
          <strong>trace_id:</strong> <code>{traceId}</code>
          {run?.trace_id === traceId && (
            <>
              {' '}
              · <strong>запуск:</strong> <code>{run.run_id}</code> · <strong>статус:</strong>{' '}
              {run.status}
            </>
          )}
        </p>
      )}

      {runEvents.length > 0 && (
        <div className="miya-trace-replay-actions">
          <button type="button" className="miya-btn miya-btn-secondary" onClick={replayOnCanvas}>
            Повторить на холсте
          </button>
          <span className="miya-run-hint">
            {runEvents.length} событий графа · клик по шагу покажет его на холсте
          </span>
        </div>
      )}

      {error && <pre className="miya-run-error">{error}</pre>}

      {traceId && !loading && !error && timeline.length === 0 && (
        <p className="miya-run-hint">
          Журнал пуст. Записи появятся после чата, запуска графа или решений безопасности.
        </p>
      )}

      {policyRows.length > 0 && (
        <div className="miya-trace-section">
          <h3 className="miya-trace-section-title">Решения безопасности</h3>
          <div className="miya-model-table-wrap">
            <table className="miya-model-table miya-policy-table">
              <thead>
                <tr>
                  <th>Время</th>
                  <th>Тип</th>
                  <th>Класс действия</th>
                  <th>Исход</th>
                  <th>Источник</th>
                </tr>
              </thead>
              <tbody>
                {policyRows.map((row) => (
                  <tr key={row.id}>
                    <td>{formatTraceTime(row.ts)}</td>
                    <td>
                      <code>{row.eventType}</code>
                    </td>
                    <td>
                      <code>{row.actionClass}</code>
                    </td>
                    <td>
                      <span className={`miya-policy-outcome ${policyOutcomeClass(row.outcome)}`}>
                        {row.outcome}
                      </span>
                    </td>
                    <td>{row.actor}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {timeline.length > 0 && (
        <div className="miya-trace-section">
          <h3 className="miya-trace-section-title">Журнал запуска</h3>
          <ol className="miya-trace-timeline">
            {timeline.map((item) => (
              <li
                key={item.id}
                className={`miya-trace-timeline-item miya-trace-${item.source}${
                  item.source === 'run' ? ' miya-trace-timeline-clickable' : ''
                }`}
                onClick={item.source === 'run' ? () => scrubRunEvent(item.id) : undefined}
                onKeyDown={
                  item.source === 'run'
                    ? (event) => {
                        if (event.key === 'Enter' || event.key === ' ') {
                          event.preventDefault();
                          scrubRunEvent(item.id);
                        }
                      }
                    : undefined
                }
                role={item.source === 'run' ? 'button' : undefined}
                tabIndex={item.source === 'run' ? 0 : undefined}
              >
                <span className="miya-trace-time">{formatTraceTime(item.ts)}</span>
                <code className="miya-trace-type">{item.kind}</code>
                <span className="miya-trace-actor">{item.actor}</span>
                <span className="miya-trace-summary">
                  {item.summary}
                  {item.nodeId ? (
                    <>
                      {' '}
                      · <code>{item.nodeId}</code>
                    </>
                  ) : null}
                </span>
              </li>
            ))}
          </ol>
        </div>
      )}
    </section>
  );
}
