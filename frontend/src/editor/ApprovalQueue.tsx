import { useCallback, useEffect, useState } from 'react';
import {
  fetchApprovals,
  resolveApproval,
  type MiaosApprovalRequest,
  type MiaosGraphRun,
} from './miaosApi';

interface ApprovalQueueProps {
  lastRun: MiaosGraphRun | null;
  onRunUpdate?: (run: MiaosGraphRun) => void;
}

function formatTs(ts: string) {
  try {
    return new Date(ts).toLocaleString();
  } catch {
    return ts;
  }
}

function actionClassLabel(actionClass: string): string {
  if (actionClass === 'publish') return 'Публикация';
  if (actionClass === 'send_message') return 'Отправка сообщения';
  if (actionClass === 'delete') return 'Удаление';
  if (actionClass === 'write_outside_sandbox') return 'Запись вне песочницы';
  return actionClass;
}

export function ApprovalQueue({ lastRun, onRunUpdate }: ApprovalQueueProps) {
  const [items, setItems] = useState<MiaosApprovalRequest[]>([]);
  const [loading, setLoading] = useState(false);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const pending = await fetchApprovals('pending');
      setItems(pending);
    } catch (err) {
      setItems([]);
      setError(err instanceof Error ? err.message : 'Не удалось загрузить очередь');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  useEffect(() => {
    if (lastRun?.status === 'waiting_for_approval') {
      void refresh();
    }
  }, [lastRun, refresh]);

  const handleResolve = async (requestId: string, decision: 'approved' | 'rejected') => {
    setBusyId(requestId);
    setError(null);
    setMessage(null);
    try {
      const result = await resolveApproval(requestId, decision);
      if (result.resumed_run) {
        onRunUpdate?.(result.resumed_run);
        setMessage(`Граф продолжен после одобрения: ${result.resumed_run.status}`);
      } else {
        setMessage(
          decision === 'approved'
            ? 'Запрос одобрен, но граф не был продолжён (нет сохранённого spec).'
            : 'Запрос отклонён — выполнение остановлено.',
        );
      }
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Не удалось обработать запрос');
    } finally {
      setBusyId(null);
    }
  };

  return (
    <section id="miya-approval-queue" className="miya-approval-queue">
      <div className="miya-run-header">
        <h2 className="miya-run-title">Очередь подтверждений</h2>
        <span className="miya-run-badge">{items.length} ожидают решения</span>
        <button
          type="button"
          className="miya-btn miya-btn-secondary"
          onClick={() => void refresh()}
          disabled={loading}
        >
          {loading ? 'Загрузка…' : 'Обновить'}
        </button>
      </div>

      <p className="miya-run-hint">
        Здесь появляются действия, которым нужно решение человека. После кнопки
        <strong> Одобрить</strong> граф продолжит выполнение, после отклонения остановится.
      </p>

      {lastRun?.approval_request_id && (
        <p className="miya-approval-latest">
          Последний запуск ждёт подтверждения.
        </p>
      )}

      {message && <p className="miya-approval-message">{message}</p>}
      {error && <pre className="miya-run-error">{error}</pre>}

      {!loading && items.length === 0 && (
        <p className="miya-run-hint">
          Очередь пуста. Соберите граф Старт → агент → согласование → Финиш и нажмите{' '}
          <strong>Запустить</strong>.
        </p>
      )}

      {items.length > 0 && (
        <ul className="miya-approval-list">
          {items.map((item) => (
            <li key={item.request_id} className="miya-approval-card">
              <div className="miya-approval-card-head">
                <strong>{actionClassLabel(item.action_class)}</strong>
                <span>{formatTs(item.created_at)}</span>
              </div>
              <p className="miya-approval-summary">{item.summary}</p>
              <dl className="miya-approval-meta">
                <div>
                  <dt>узел</dt>
                  <dd>{item.node_id}</dd>
                </div>
              </dl>
              <div className="miya-approval-actions">
                <button
                  type="button"
                  className="miya-btn miya-btn-primary"
                  disabled={busyId === item.request_id}
                  onClick={() => void handleResolve(item.request_id, 'approved')}
                >
                  Одобрить
                </button>
                <button
                  type="button"
                  className="miya-btn miya-btn-danger"
                  disabled={busyId === item.request_id}
                  onClick={() => void handleResolve(item.request_id, 'rejected')}
                >
                  Отклонить
                </button>
              </div>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
