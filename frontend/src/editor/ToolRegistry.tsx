import { useCallback, useEffect, useState } from 'react';
import { fetchTools, type MiaosToolSpec } from './miaosApi';

export function ToolRegistry() {
  const [tools, setTools] = useState<MiaosToolSpec[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const list = await fetchTools();
      setTools(list);
    } catch (err) {
      setTools([]);
      setError(err instanceof Error ? err.message : 'Не удалось загрузить инструменты');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  useEffect(() => {
    const onRefresh = () => void refresh();
    window.addEventListener('miya:studio-refresh', onRefresh);
    return () => window.removeEventListener('miya:studio-refresh', onRefresh);
  }, [refresh]);

  return (
    <section id="miya-tool-registry" className="miya-tool-registry">
      <div className="miya-run-header">
        <h2 className="miya-run-title">Инструменты</h2>
        <span className="miya-run-badge">{tools.length} инструментов</span>
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
        Каталог инструментов, которые можно вызывать из графа. Они проходят проверку безопасности
        и выполняются только в sandbox-режиме.
      </p>

      {error && <pre className="miya-run-error">{error}</pre>}

      {!loading && !error && tools.length === 0 && (
        <p className="miya-run-hint">
          Реестр пуст. Перезапустите backend с новым кодом MiaOS.
        </p>
      )}

      {tools.length > 0 && (
        <div className="miya-model-table-wrap">
          <table className="miya-model-table">
            <thead>
              <tr>
                <th>Инструмент</th>
                <th>Класс действия</th>
                <th>Песочница</th>
                <th>Статус</th>
              </tr>
            </thead>
            <tbody>
              {tools.map((tool) => (
                <tr key={tool.name}>
                  <td>
                    <strong>{tool.name}</strong>
                    <div className="miya-model-id">{tool.description}</div>
                  </td>
                  <td>
                    <code>{tool.action_class}</code>
                  </td>
                  <td>{tool.sandbox_only ? 'да' : 'нет'}</td>
                  <td>
                    <span
                      className={`miya-model-status ${
                        tool.enabled ? 'miya-model-status-active' : 'miya-model-status-archived'
                      }`}
                    >
                      {tool.enabled ? 'включён' : 'выключен'}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
