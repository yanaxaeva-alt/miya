import { useCallback, useEffect, useMemo, useState } from 'react';
import {
  deleteDemoModels,
  fetchModelCompatibility,
  fetchModels,
  registerMiaosModel,
  setModelLabCert,
  type MiaosLabCertStatus,
  type MiaosModelCompatibilityReport,
  type MiaosModelRecord,
} from './miaosApi';
import { DEMO_MODELS } from './demoAssets';
import { getSelectedRuntimeProfile } from './editorPrefs';

interface ModelStudioProps {
  models: MiaosModelRecord[];
  onModelsChange: (models: MiaosModelRecord[]) => void;
}

const LAB_CERT_OPTIONS: Array<{ value: MiaosLabCertStatus | ''; label: string }> = [
  { value: '', label: '—' },
  { value: 'pending', label: 'pending' },
  { value: 'passed', label: 'passed' },
  { value: 'certified', label: 'certified' },
  { value: 'conditional', label: 'conditional' },
  { value: 'failed', label: 'failed' },
  { value: 'rejected', label: 'rejected' },
];

const POOL_ROLES = ['router', 'worker', 'moe_expert', 'deep'] as const;

function formatSizeGb(sizeBytes: number): string {
  return `${(sizeBytes / 1_000_000_000).toFixed(1)} GB`;
}

function modelLabel(record: MiaosModelRecord): string {
  return record.repo || `${record.family} ${record.params_billion}B`;
}

function warningSummary(report: MiaosModelCompatibilityReport | undefined): string {
  if (!report) return '—';
  if (report.recommended) return 'recommended';
  if (report.warnings.length === 0) return 'ok';
  const top = report.warnings.find((warning) => warning.severity === 'error') ?? report.warnings[0];
  return top.code;
}

function warningClass(report: MiaosModelCompatibilityReport | undefined): string {
  if (!report) return 'miya-compat-unknown';
  if (report.recommended) return 'miya-compat-recommended';
  if (!report.compatible) return 'miya-compat-error';
  if (report.warnings.some((warning) => warning.severity === 'warning')) {
    return 'miya-compat-warning';
  }
  return 'miya-compat-ok';
}

export function ModelStudio({ models, onModelsChange }: ModelStudioProps) {
  const [loading, setLoading] = useState(false);
  const [seeding, setSeeding] = useState(false);
  const [cleaning, setCleaning] = useState(false);
  const [certUpdatingId, setCertUpdatingId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [profileName, setProfileName] = useState(
    () => getSelectedRuntimeProfile() || 'macbook_air_m4_32gb',
  );
  const [poolRole, setPoolRole] = useState<(typeof POOL_ROLES)[number]>('worker');
  const [compatibility, setCompatibility] = useState<MiaosModelCompatibilityReport[]>([]);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const list = await fetchModels();
      onModelsChange(list);
    } catch (err) {
      onModelsChange([]);
      setError(err instanceof Error ? err.message : 'Не удалось загрузить модели');
    } finally {
      setLoading(false);
    }
  }, [onModelsChange]);

  const refreshCompatibility = useCallback(async () => {
    if (!profileName) {
      setCompatibility([]);
      return;
    }
    try {
      const reports = await fetchModelCompatibility(profileName, poolRole);
      setCompatibility(reports);
    } catch (err) {
      setCompatibility([]);
      setError(err instanceof Error ? err.message : 'Не удалось проверить совместимость');
    }
  }, [profileName, poolRole]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  useEffect(() => {
    void refreshCompatibility();
  }, [refreshCompatibility, models.length]);

  useEffect(() => {
    const onRefresh = () => {
      setProfileName(getSelectedRuntimeProfile() || 'macbook_air_m4_32gb');
      void refresh();
    };
    window.addEventListener('miya:studio-refresh', onRefresh);
    window.addEventListener('miya:runtime-profile-changed', onRefresh);
    return () => {
      window.removeEventListener('miya:studio-refresh', onRefresh);
      window.removeEventListener('miya:runtime-profile-changed', onRefresh);
    };
  }, [refresh]);

  const compatibilityById = useMemo(
    () => new Map(compatibility.map((report) => [report.model_id, report])),
    [compatibility],
  );

  const summary = useMemo(() => {
    const selectable = compatibility.filter((report) => report.selectable).length;
    const warnings = compatibility.filter((report) =>
      report.warnings.some((warning) => warning.severity !== 'info'),
    ).length;
    const recommended = compatibility.find((report) => report.recommended);
    return { selectable, warnings, recommended };
  }, [compatibility]);

  const seedDemoModels = useCallback(async () => {
    setSeeding(true);
    setError(null);
    setMessage(null);
    try {
      const existing = await fetchModels();
      const existingRepos = new Set(existing.map((model) => model.repo));
      let created = 0;
      for (const payload of DEMO_MODELS) {
        if (existingRepos.has(payload.repo)) continue;
        await registerMiaosModel(payload);
        existingRepos.add(payload.repo);
        created += 1;
      }
      if (created === 0) {
        setMessage('Демо-модели уже зарегистрированы; новые дубликаты не добавлены.');
      } else {
        setMessage(`Добавлено демо-моделей: ${created}.`);
      }
      await refresh();
      await refreshCompatibility();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Не удалось зарегистрировать демо-модели');
    } finally {
      setSeeding(false);
    }
  }, [refresh, refreshCompatibility]);

  const updateLabCert = useCallback(
    async (modelId: string, labCert: MiaosLabCertStatus | null) => {
      setCertUpdatingId(modelId);
      setError(null);
      setMessage(null);
      try {
        await setModelLabCert(modelId, labCert);
        await refresh();
        await refreshCompatibility();
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Не удалось обновить lab cert');
      } finally {
        setCertUpdatingId(null);
      }
    },
    [refresh, refreshCompatibility],
  );

  const cleanDemoModels = useCallback(async () => {
    setCleaning(true);
    setError(null);
    setMessage(null);
    try {
      const result = await deleteDemoModels();
      setMessage(`Удалено демо-моделей: ${result.deleted}.`);
      await refresh();
      await refreshCompatibility();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Не удалось очистить демо-модели');
    } finally {
      setCleaning(false);
    }
  }, [refresh, refreshCompatibility]);

  return (
    <section id="miya-model-studio" className="miya-model-studio">
      <div className="miya-run-header">
        <h2 className="miya-run-title">Model Studio</h2>
        <span className="miya-run-badge">{models.length} models</span>
        {summary.recommended && (
          <span className="miya-run-badge miya-run-badge-ok">
            recommended: {summary.recommended.model_id.slice(0, 8)}…
          </span>
        )}
        <button
          type="button"
          className="miya-btn miya-btn-secondary"
          onClick={() => {
            void refresh();
            void refreshCompatibility();
          }}
          disabled={loading || seeding || cleaning}
        >
          {loading ? 'Загрузка…' : 'Обновить'}
        </button>
        <button
          type="button"
          className="miya-btn"
          onClick={() => void seedDemoModels()}
          disabled={loading || seeding || cleaning}
        >
          {seeding ? 'Регистрация…' : 'Демо-модели'}
        </button>
        <button
          type="button"
          className="miya-btn miya-btn-danger"
          onClick={() => void cleanDemoModels()}
          disabled={loading || seeding || cleaning}
        >
          {cleaning ? 'Очистка…' : 'Очистить демо'}
        </button>
      </div>

      <p className="miya-run-hint">
        Реестр из <code>GET /models</code> с проверкой против runtime profile (
        <code>GET /models/compatibility</code>) и управлением lab certification (
        <code>PATCH /models/&#123;id&#125;/lab-cert</code>).
      </p>

      <div className="miya-model-compat-controls">
        <label className="miya-field miya-model-compat-field">
          <span>Runtime profile</span>
          <input type="text" value={profileName} readOnly />
        </label>
        <label className="miya-field miya-model-compat-field">
          <span>Pool role</span>
          <select
            value={poolRole}
            onChange={(event) =>
              setPoolRole(event.target.value as (typeof POOL_ROLES)[number])
            }
          >
            {POOL_ROLES.map((role) => (
              <option key={role} value={role}>
                {role}
              </option>
            ))}
          </select>
        </label>
        <p className="miya-run-hint miya-model-compat-summary">
          selectable: {summary.selectable}/{compatibility.length || models.length} · warnings:{' '}
          {summary.warnings}
        </p>
      </div>

      {error && <pre className="miya-run-error">{error}</pre>}
      {message && <p className="miya-persona-message">{message}</p>}

      {!loading && !error && models.length === 0 && (
        <p className="miya-run-hint">
          Реестр пуст. Нажмите <strong>Демо-модели</strong> или зарегистрируйте модель через{' '}
          <code>POST /models/register</code>.
        </p>
      )}

      {models.length > 0 && (
        <div className="miya-model-table-wrap">
          <table className="miya-model-table">
            <thead>
              <tr>
                <th>Модель</th>
                <th>Quant</th>
                <th>Context</th>
                <th>Размер</th>
                <th>Роль</th>
                <th>Совместимость</th>
                <th>Lab cert</th>
              </tr>
            </thead>
            <tbody>
              {models.map((model) => {
                const report = compatibilityById.get(model.id);
                return (
                  <tr key={model.id} className={report?.compatible === false ? 'miya-model-row-bad' : ''}>
                    <td>
                      <strong>{modelLabel(model)}</strong>
                      <div className="miya-model-id">
                        <code>{model.id}</code>
                      </div>
                      {report && report.warnings.length > 0 && (
                        <ul className="miya-compat-warnings">
                          {report.warnings.map((warning) => (
                            <li
                              key={`${warning.code}-${warning.message}`}
                              className={`miya-compat-item miya-compat-item-${warning.severity}`}
                            >
                              {warning.message}
                            </li>
                          ))}
                        </ul>
                      )}
                    </td>
                    <td>{model.quant}</td>
                    <td>{model.context_len.toLocaleString()}</td>
                    <td>{formatSizeGb(model.size_bytes)}</td>
                    <td>{model.pool_role || '—'}</td>
                    <td>
                      <span className={`miya-compat-badge ${warningClass(report)}`}>
                        {warningSummary(report)}
                      </span>
                    </td>
                    <td>
                      <select
                        className="miya-lab-cert-select"
                        value={model.lab_cert || ''}
                        disabled={certUpdatingId === model.id}
                        onChange={(event) => {
                          const value = event.target.value;
                          void updateLabCert(
                            model.id,
                            value ? (value as MiaosLabCertStatus) : null,
                          );
                        }}
                      >
                        {LAB_CERT_OPTIONS.map((option) => (
                          <option key={option.label} value={option.value}>
                            {option.label}
                          </option>
                        ))}
                      </select>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
