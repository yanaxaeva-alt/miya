import { useCallback, useEffect, useMemo, useState } from 'react';
import {
  deleteDemoModels,
  fetchModelCompatibility,
  fetchModels,
  fetchProviders,
  registerMiaosModel,
  setModelLabCert,
  setOmlxDefaultModel,
  type MiaosLabCertStatus,
  type MiaosModelCompatibilityReport,
  type MiaosModelRecord,
  type MiaosProviderInfo,
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
  const [switchingModel, setSwitchingModel] = useState(false);
  const [certUpdatingId, setCertUpdatingId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [profileName, setProfileName] = useState(
    () => getSelectedRuntimeProfile() || 'macbook_air_m4_32gb',
  );
  const [poolRole, setPoolRole] = useState<(typeof POOL_ROLES)[number]>('worker');
  const [compatibility, setCompatibility] = useState<MiaosModelCompatibilityReport[]>([]);
  const [providers, setProviders] = useState<MiaosProviderInfo[]>([]);
  const [selectedOmlxModel, setSelectedOmlxModel] = useState('');

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const list = await fetchModels();
      onModelsChange(list);
      const providerList = await fetchProviders();
      setProviders(providerList);
      const omlx = providerList.find((provider) => provider.name === 'omlx');
      setSelectedOmlxModel((prev) => prev || omlx?.default_model || omlx?.model_ids?.[0] || '');
    } catch (err) {
      onModelsChange([]);
      setProviders([]);
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

  const mlxProvider = providers.find((provider) => provider.name === 'mlx');
  const omlxProvider = providers.find((provider) => provider.name === 'omlx');
  const activeProvider =
    providers.find((provider) => provider.default && provider.available) ??
    providers.find((provider) => provider.available);
  const omlxModelIds = omlxProvider?.model_ids ?? [];

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

  const selectOmlxModel = useCallback(async () => {
    if (!selectedOmlxModel) return;
    setSwitchingModel(true);
    setError(null);
    setMessage(null);
    try {
      const providerList = await setOmlxDefaultModel(selectedOmlxModel);
      setProviders(providerList);
      setMessage(`oMLX model saved: ${selectedOmlxModel}`);
      window.dispatchEvent(new CustomEvent('miya:studio-refresh'));
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Не удалось выбрать oMLX модель');
    } finally {
      setSwitchingModel(false);
    }
  }, [selectedOmlxModel]);

  return (
    <section id="miya-model-studio" className="miya-model-studio">
      <div className="miya-run-header">
        <h2 className="miya-run-title">Model Studio</h2>
        <span className="miya-run-badge">provider: {activeProvider?.name ?? 'unknown'}</span>
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
      </div>

      <section className="miya-model-primary-card">
        <div>
          <span className="miya-aeon-status-label">Основная модель для Mia / AEON</span>
          <h3>{omlxProvider?.default_model ?? 'Модель не выбрана'}</h3>
          <p>
            Если oMLX скачал несколько моделей, выберите одну здесь. MiaOS будет отправлять запросы
            в oMLX на <code>127.0.0.1:8010</code>, модель не копируется в этот проект.
          </p>
        </div>
        <div className="miya-model-select-row">
          <label className="miya-field miya-model-select-field">
            <span>oMLX model</span>
            <select
              value={selectedOmlxModel}
              onChange={(event) => setSelectedOmlxModel(event.target.value)}
              disabled={!omlxProvider?.available || omlxModelIds.length === 0 || switchingModel}
            >
              {omlxModelIds.length === 0 ? (
                <option value="">Нет моделей из /v1/models</option>
              ) : (
                omlxModelIds.map((modelId) => (
                  <option key={modelId} value={modelId}>
                    {modelId}
                  </option>
                ))
              )}
            </select>
          </label>
          <button
            type="button"
            className="miya-btn miya-btn-primary"
            onClick={() => void selectOmlxModel()}
            disabled={
              switchingModel ||
              !selectedOmlxModel ||
              selectedOmlxModel === omlxProvider?.default_model
            }
          >
            {switchingModel ? 'Выбираю…' : 'Использовать'}
          </button>
        </div>
        <p className="miya-run-provider-hint">
          oMLX: {omlxProvider?.available ? omlxProvider.description : 'недоступен'}
          {mlxProvider ? (
            <>
              <br />
              MLX fallback: {mlxProvider.available ? mlxProvider.description : 'недоступен'}
            </>
          ) : null}
        </p>
      </section>

      <section className="miya-model-mode-help">
        <div>
          <strong>oMLX</strong>
          <p>Реальная локальная модель. Используйте для обычной работы Mia и AEON.</p>
        </div>
        <div>
          <strong>MLX fallback</strong>
          <p>Прямой запуск через <code>mlx-lm</code>, если oMLX не нужен.</p>
        </div>
        <div>
          <strong>Demo-модели</strong>
          <p>Тестовые записи реестра для проверки совместимости. Они не скачивают модель.</p>
        </div>
      </section>

      {error && <pre className="miya-run-error">{error}</pre>}
      {message && <p className="miya-persona-message">{message}</p>}

      <details className="miya-advanced-section">
        <summary>Advanced: demo registry, pool roles, lab certification</summary>
        <div className="miya-advanced-section-body">
          <p className="miya-run-hint">
            Этот раздел нужен для разработки: демо-модели — это metadata-записи в <code>GET /models</code>,
            pool role показывает предполагаемую роль модели, lab cert — ручная отметка качества.
          </p>
          <div className="miya-run-actions">
            <button
              type="button"
              className="miya-btn"
              onClick={() => void seedDemoModels()}
              disabled={loading || seeding || cleaning}
            >
              {seeding ? 'Регистрация…' : 'Добавить demo-модели'}
            </button>
            <button
              type="button"
              className="miya-btn miya-btn-danger"
              onClick={() => void cleanDemoModels()}
              disabled={loading || seeding || cleaning}
            >
              {cleaning ? 'Очистка…' : 'Очистить demo'}
            </button>
          </div>

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

          {!loading && !error && models.length === 0 && (
            <p className="miya-run-hint">
              Реестр пуст. Нажмите <strong>Добавить demo-модели</strong> или зарегистрируйте модель через{' '}
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
        </div>
      </details>
    </section>
  );
}
