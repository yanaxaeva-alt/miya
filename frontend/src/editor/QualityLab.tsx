import { useCallback, useEffect, useState } from 'react';
import {
  fetchProviders,
  fetchQualityDatasets,
  runQualityEval,
  type MiaosEvalReport,
  type MiaosProviderInfo,
  type MiaosQualityDataset,
} from './miaosApi';
import { DEFAULT_PROVIDER, pickDefaultProvider, providerDisplayName } from './providerPrefs';

function datasetDescription(dataset: MiaosQualityDataset): string {
  if (dataset.name === 'golden_mvp') {
    return 'Базовый набор: проверяет стабильность персоны, границы безопасности и регрессии графов.';
  }
  return dataset.description;
}

function suiteLabel(suite: string): string {
  if (suite === 'persona_consistency') return 'персона';
  if (suite === 'safety_boundary') return 'безопасность';
  if (suite === 'graph_regression') return 'графы';
  return suite;
}

export function QualityLab() {
  const [datasets, setDatasets] = useState<MiaosQualityDataset[]>([]);
  const [providers, setProviders] = useState<MiaosProviderInfo[]>([]);
  const [selectedDataset, setSelectedDataset] = useState('golden_mvp');
  const [selectedProvider, setSelectedProvider] = useState(DEFAULT_PROVIDER);
  const [report, setReport] = useState<MiaosEvalReport | null>(null);
  const [loading, setLoading] = useState(false);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [datasetList, providerList] = await Promise.all([
        fetchQualityDatasets(),
        fetchProviders(),
      ]);
      setDatasets(datasetList);
      setProviders(providerList);
      if (datasetList.length > 0 && !datasetList.some((item) => item.name === selectedDataset)) {
        setSelectedDataset(datasetList[0].name);
      }
      setSelectedProvider((prev) => {
        const current = providerList.find((item) => item.name === prev);
        if (current?.available) return prev;
        return pickDefaultProvider(providerList);
      });
    } catch (err) {
      setDatasets([]);
      setError(err instanceof Error ? err.message : 'Не удалось загрузить проверки качества');
    } finally {
      setLoading(false);
    }
  }, [selectedDataset]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const runEval = useCallback(async () => {
    setRunning(true);
    setError(null);
    setReport(null);
    try {
      const result = await runQualityEval(selectedDataset, selectedProvider, 'mia');
      setReport(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Не удалось запустить проверку');
    } finally {
      setRunning(false);
    }
  }, [selectedDataset, selectedProvider]);

  const activeDataset = datasets.find((item) => item.name === selectedDataset);

  return (
    <section id="miya-quality-lab" className="miya-quality-lab">
      <div className="miya-run-header">
        <h2 className="miya-run-title">Проверка качества</h2>
        <span className="miya-run-badge">{activeDataset?.case_count ?? 0} кейсов</span>
        <button
          type="button"
          className="miya-btn miya-btn-secondary"
          onClick={() => void refresh()}
          disabled={loading || running}
        >
          {loading ? 'Загрузка…' : 'Обновить'}
        </button>
        <button
          type="button"
          className="miya-btn miya-btn-primary"
          onClick={() => void runEval()}
          disabled={running || datasets.length === 0}
        >
          {running ? 'Проверка…' : 'Запустить проверку'}
        </button>
      </div>

      <p className="miya-run-hint">
        Быстрая проверка, что Mia отвечает стабильно, соблюдает границы безопасности и не ломает
        базовые графы. Для локальной модели проверяем, что ответ пришёл и сценарий завершился.
      </p>

      {selectedProvider !== 'mock' && (
        <p className="miya-run-hint">
          Провайдер <strong>{providerDisplayName(selectedProvider)}</strong>: проверка не сравнивает
          текст дословно, а убеждается, что локальная модель вернула осмысленный ответ.
        </p>
      )}

      <div className="miya-chat-controls">
        <label className="miya-field">
          <span>Набор проверок</span>
          <select
            value={selectedDataset}
            onChange={(e) => setSelectedDataset(e.target.value)}
            disabled={running}
          >
            {datasets.map((dataset) => (
              <option key={dataset.name} value={dataset.name}>
                {dataset.name} ({dataset.case_count})
              </option>
            ))}
          </select>
        </label>
        <label className="miya-field">
          <span>Провайдер</span>
          <select
            value={selectedProvider}
            onChange={(e) => setSelectedProvider(e.target.value)}
            disabled={running}
          >
            {providers.map((provider) => (
              <option key={provider.name} value={provider.name} disabled={!provider.available}>
                {providerDisplayName(provider.name)}
                {!provider.available ? ' (недоступен)' : ''}
              </option>
            ))}
          </select>
        </label>
      </div>

      {activeDataset && (
        <p className="miya-run-hint">
          {datasetDescription(activeDataset)} · порог {Math.round(activeDataset.min_pass_rate * 100)}% · группы:{' '}
          {activeDataset.suites.map(suiteLabel).join(', ')}
        </p>
      )}

      {error && <pre className="miya-run-error">{error}</pre>}

      {report && (
        <div className={`miya-quality-summary ${report.gate_passed ? 'miya-quality-pass' : 'miya-quality-fail'}`}>
          <strong>{report.gate_passed ? 'ПРОЙДЕНО' : 'ЕСТЬ ПРОБЛЕМЫ'}</strong> · {report.passed}/
          {report.passed + report.failed} пройдено · {Math.round(report.pass_rate * 100)}% (минимум{' '}
          {Math.round(report.min_pass_rate * 100)}%)
        </div>
      )}

      {report && report.results.length > 0 && (
        <div className="miya-model-table-wrap">
          <table className="miya-model-table">
            <thead>
              <tr>
                <th>Кейс</th>
                <th>Группа</th>
                <th>Исход</th>
                <th>Детали</th>
              </tr>
            </thead>
            <tbody>
              {report.results.map((result) => (
                <tr key={result.case_id}>
                  <td>
                    <code>{result.case_id}</code>
                  </td>
                  <td>{suiteLabel(result.suite)}</td>
                  <td>
                    <span
                      className={`miya-model-status ${
                        result.passed ? 'miya-model-status-active' : 'miya-model-status-archived'
                      }`}
                    >
                      {result.passed ? 'пройден' : 'ошибка'}
                    </span>
                  </td>
                  <td>{result.detail}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
