import { useCallback, useEffect, useState } from 'react';
import type { Graph } from '@antv/x6';
import type { MiaosGraphRun, MiaosModelRecord } from './miaosApi';
import {
  bootstrapMiaMinimal,
  fetchMiaScenarioStatus,
  scrollToPanel,
  type MiaScenarioStatus,
} from './miaMinimalSetup';
import { setStatus } from '../miyaBridge';

interface MiaScenarioProps {
  graph: Graph | null;
  lastRun: MiaosGraphRun | null;
  onModelsChange: (models: MiaosModelRecord[]) => void;
  compact?: boolean;
}

function StepRow({
  done,
  label,
  actionLabel,
  onAction,
}: {
  done: boolean;
  label: string;
  actionLabel?: string;
  onAction?: () => void;
}) {
  return (
    <li className={`miya-scenario-step ${done ? 'miya-scenario-step-done' : ''}`}>
      <span className="miya-scenario-step-mark">{done ? '✓' : '○'}</span>
      <span className="miya-scenario-step-label">{label}</span>
      {!done && actionLabel && onAction && (
        <button type="button" className="miya-btn miya-btn-secondary miya-scenario-step-btn" onClick={onAction}>
          {actionLabel}
        </button>
      )}
    </li>
  );
}

export function MiaScenario({ graph, lastRun, onModelsChange, compact = false }: MiaScenarioProps) {
  const [status, setScenarioStatus] = useState<MiaScenarioStatus | null>(null);
  const [loading, setLoading] = useState(false);
  const [bootstrapping, setBootstrapping] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const next = await fetchMiaScenarioStatus(graph, lastRun);
      setScenarioStatus(next);
    } catch (err) {
      setScenarioStatus(null);
      setError(err instanceof Error ? err.message : 'Не удалось проверить сценарий');
    } finally {
      setLoading(false);
    }
  }, [graph, lastRun]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  useEffect(() => {
    const onRefresh = () => void refresh();
    window.addEventListener('miya:studio-refresh', onRefresh);
    window.addEventListener('miya:aeon-ask', onRefresh);
    window.addEventListener('miya:aeon-goal-added', onRefresh);
    window.addEventListener('miya:aeon-consolidated', onRefresh);
    return () => {
      window.removeEventListener('miya:studio-refresh', onRefresh);
      window.removeEventListener('miya:aeon-ask', onRefresh);
      window.removeEventListener('miya:aeon-goal-added', onRefresh);
      window.removeEventListener('miya:aeon-consolidated', onRefresh);
    };
  }, [refresh]);

  const runBootstrap = useCallback(
    async (replaceCanvas = false) => {
      if (replaceCanvas && graph && graph.getNodes().length > 0) {
        if (!window.confirm('Заменить текущий граф шаблоном Mia Minimal?')) return;
      }
      setBootstrapping(true);
      setError(null);
      setMessage(null);
      try {
        const result = await bootstrapMiaMinimal(graph, { replaceCanvas });
        onModelsChange(result.models);
        setMessage(result.steps.join('\n'));
        setStatus(`Mia Minimal: ${result.provider}`);
        await refresh();
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Не удалось подготовить сценарий');
      } finally {
        setBootstrapping(false);
      }
    },
    [graph, onModelsChange, refresh],
  );

  const setupReady =
    status?.online &&
    status.runtimeProfileSelected &&
    status.templateRegistryReady &&
    status.modelsReady &&
    status.personaReady &&
    status.libraryReady &&
    status.canvasReady;

  return (
    <section id="miya-scenario" className={`miya-scenario${compact ? ' miya-scenario-compact' : ''}`}>
      <div className="miya-run-header">
        <h2 className="miya-run-title">{compact ? 'Чеклист сценария' : 'Сценарий v1.0'}</h2>
        <span className="miya-run-badge">{setupReady ? 'готов' : 'настройка'}</span>
        <button
          type="button"
          className="miya-btn miya-btn-secondary"
          onClick={() => void refresh()}
          disabled={loading || bootstrapping}
        >
          {loading ? 'Проверка…' : 'Обновить'}
        </button>
        <button
          type="button"
          className="miya-btn miya-btn-primary"
          onClick={() => void runBootstrap(false)}
          disabled={bootstrapping}
        >
          {bootstrapping ? 'Подготовка…' : 'Подготовить всё'}
        </button>
      </div>

      {!compact && (
        <p className="miya-run-hint">
          Сквозной сценарий v1.0: профиль компьютера, шаблоны, модели, персона,
          граф, библиотека, чат, запуск и подтверждение.
          Провайдер: <strong>{status?.provider ?? '…'}</strong>
          {status?.mlxAvailable ? ' (MLX)' : ' (mock)'}.
        </p>
      )}

      {message && <p className="miya-persona-message">{message}</p>}
      {error && <pre className="miya-run-error">{error}</pre>}

      <ol className="miya-scenario-steps">
        {compact ? (
          <>
            <StepRow done={Boolean(status?.online)} label="Локальный MiaOS доступен" />
            <StepRow
              done={Boolean(status?.aeonOnline)}
              label="AEON готов"
              actionLabel="К AEON"
              onAction={() => scrollToPanel('miya-aeon-studio')}
            />
            <StepRow
              done={Boolean(status?.aeonResponded)}
              label="AEON ответил"
              actionLabel="Спросить"
              onAction={() => scrollToPanel('miya-aeon-studio')}
            />
            <StepRow done={Boolean(status?.aeonGoalAdded)} label="Добавлена цель" />
            <StepRow done={Boolean(status?.aeonConsolidated)} label="Память закреплена" />
          </>
        ) : (
          <>
            <StepRow done={Boolean(status?.online)} label="Локальный MiaOS доступен" />
            <StepRow
              done={Boolean(status?.runtimeProfileSelected)}
              label="Выбран профиль компьютера"
              actionLabel="К профилю"
              onAction={() => scrollToPanel('miya-runtime-profile')}
            />
            <StepRow
              done={Boolean(status?.templateRegistryReady)}
              label="Шаблон Mia Minimal доступен"
              actionLabel="К шаблонам"
              onAction={() => scrollToPanel('miya-template-registry')}
            />
            <StepRow
              done={Boolean(status?.modelsReady)}
              label={`Модели доступны (${status?.modelCount ?? 0})`}
            />
            <StepRow done={Boolean(status?.personaReady)} label="Персона Mia готова" />
            <StepRow done={Boolean(status?.canvasReady)} label="Холст — шаблон Mia Minimal" />
            <StepRow done={Boolean(status?.libraryReady)} label="Граф сохранён в библиотеке" />
            <StepRow
              done={Boolean(status?.runWaitingApproval || status?.runCompleted)}
              label="Сценарий запущен"
              actionLabel="К запуску"
              onAction={() => scrollToPanel('miya-run-console')}
            />
            <StepRow
              done={Boolean(status?.runCompleted)}
              label="Подтверждение обработано"
              actionLabel="К подтверждению"
              onAction={() => scrollToPanel('miya-approval-queue')}
            />
            <StepRow
              done={Boolean(status?.aeonOnline)}
              label="AEON готов"
              actionLabel="К AEON"
              onAction={() => scrollToPanel('miya-aeon-studio')}
            />
            <StepRow
              done={Boolean(status?.aeonResponded)}
              label="AEON ответил"
              actionLabel="Спросить AEON"
              onAction={() => scrollToPanel('miya-aeon-studio')}
            />
            <StepRow done={Boolean(status?.aeonGoalAdded)} label="AEON запомнил цель" />
            <StepRow done={Boolean(status?.aeonConsolidated)} label="AEON закрепил память" />
          </>
        )}
      </ol>

      {!compact && (
        <div className="miya-scenario-actions">
          <button type="button" className="miya-btn" onClick={() => scrollToPanel('miya-chat-studio')}>
            Чат
          </button>
          <button type="button" className="miya-btn" onClick={() => scrollToPanel('miya-run-console')}>
            Запуск
          </button>
          <button
            type="button"
            className="miya-btn miya-btn-secondary"
            onClick={() => void runBootstrap(true)}
            disabled={bootstrapping || !graph}
          >
            Перезагрузить шаблон
          </button>
        </div>
      )}
    </section>
  );
}
