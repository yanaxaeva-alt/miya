import { useCallback, useEffect, useState } from 'react';
import {
  fetchProviders,
  fetchQualityDatasets,
  runQualityEval,
  type MiaosEvalReport,
  type MiaosProviderInfo,
  type MiaosQualityDataset,
} from './miaosApi';
import { DEFAULT_PROVIDER, pickDefaultProvider } from './providerPrefs';

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
      setError(err instanceof Error ? err.message : 'Не удалось загрузить Quality Lab');
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
      setError(err instanceof Error ? err.message : 'Не удалось запустить eval');
    } finally {
      setRunning(false);
    }
  }, [selectedDataset, selectedProvider]);

  const activeDataset = datasets.find((item) => item.name === selectedDataset);

  return (
    <section id="miya-quality-lab" className="miya-quality-lab">
      <div className="miya-run-header">
        <h2 className="miya-run-title">Quality Lab</h2>
        <span className="miya-run-badge">{activeDataset?.case_count ?? 0} cases</span>
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
          {running ? 'Прогон…' : 'Запустить eval'}
        </button>
      </div>

      <p className="miya-run-hint">
        Golden dataset evals через <code>POST /quality/eval</code>: persona consistency, safety
        boundary, graph regression. Для chat-кейсов нужен persona package <code>mia</code>.{' '}
        <strong>mock</strong> — строгий echo-тест; <strong>mlx</strong> — smoke-тест (непустой
        ответ модели).
      </p>

      {selectedProvider !== 'mock' && (
        <p className="miya-run-hint">
          Провайдер <strong>{selectedProvider}</strong>: кейс <code>persona-echo</code> проверяет
          только что chat pipeline вернул текст, без точного совпадения с mock-echo.
        </p>
      )}

      <div className="miya-chat-controls">
        <label className="miya-field">
          <span>Dataset</span>
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
                {provider.name}
                {!provider.available ? ' (недоступен)' : ''}
              </option>
            ))}
          </select>
        </label>
      </div>

      {activeDataset && (
        <p className="miya-run-hint">
          {activeDataset.description} · порог {Math.round(activeDataset.min_pass_rate * 100)}% · suites:{' '}
          {activeDataset.suites.join(', ')}
        </p>
      )}

      {error && <pre className="miya-run-error">{error}</pre>}

      {report && (
        <div className={`miya-quality-summary ${report.gate_passed ? 'miya-quality-pass' : 'miya-quality-fail'}`}>
          <strong>{report.gate_passed ? 'PASS' : 'FAIL'}</strong> · {report.passed}/{report.passed + report.failed}{' '}
          passed · {Math.round(report.pass_rate * 100)}% (min {Math.round(report.min_pass_rate * 100)}%)
        </div>
      )}

      {report && report.results.length > 0 && (
        <div className="miya-model-table-wrap">
          <table className="miya-model-table">
            <thead>
              <tr>
                <th>Case</th>
                <th>Suite</th>
                <th>Исход</th>
                <th>Detail</th>
              </tr>
            </thead>
            <tbody>
              {report.results.map((result) => (
                <tr key={result.case_id}>
                  <td>
                    <code>{result.case_id}</code>
                  </td>
                  <td>{result.suite}</td>
                  <td>
                    <span
                      className={`miya-model-status ${
                        result.passed ? 'miya-model-status-active' : 'miya-model-status-archived'
                      }`}
                    >
                      {result.passed ? 'pass' : 'fail'}
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
