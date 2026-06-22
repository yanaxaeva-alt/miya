import { useCallback, useEffect, useState } from 'react';
import type { Graph } from '@antv/x6';
import {
  fetchGraphLibrary,
  fetchSavedGraph,
  saveGraphToLibrary,
  type MiaosGraphLibraryItem,
} from './miaosApi';
import { exportToMiaosGraph } from './miaosExport';
import { importMiaosToCanvas } from './miaosImport';
import { setStatus } from '../miyaBridge';

interface GraphLibraryProps {
  graph: Graph | null;
}

export function GraphLibrary({ graph }: GraphLibraryProps) {
  const [items, setItems] = useState<MiaosGraphLibraryItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [loadingName, setLoadingName] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [saveName, setSaveName] = useState('mia-minimal');

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const list = await fetchGraphLibrary();
      setItems(list);
    } catch (err) {
      setItems([]);
      setError(err instanceof Error ? err.message : 'Не удалось загрузить библиотеку графов');
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

  const saveCurrentGraph = useCallback(async () => {
    if (!graph) {
      window.alert('Подождите — холст ещё загружается.');
      return;
    }
    if (graph.getNodes().length === 0) {
      window.alert('На холсте нет узлов — сохранять нечего.');
      return;
    }

    setSaving(true);
    setError(null);
    setMessage(null);
    try {
      const { spec, warnings } = exportToMiaosGraph(graph, {
        graphId: saveName.trim() || undefined,
        name: saveName.trim() || 'Miya agent graph',
      });
      const filename = saveName.trim() ? `${saveName.trim()}.json` : undefined;
      const saved = await saveGraphToLibrary(spec, filename);
      setMessage(`Сохранено: ${saved.filename} (${saved.node_count} узлов)`);
      if (warnings.length) {
        setMessage((prev) => `${prev}\nАвто-правки: ${warnings.join('; ')}`);
      }
      setStatus(`Graph Library: ${saved.filename}`);
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Не удалось сохранить граф');
    } finally {
      setSaving(false);
    }
  }, [graph, refresh, saveName]);

  const loadOntoCanvas = useCallback(
    async (filename: string) => {
      if (!graph) {
        window.alert('Подождите — холст ещё загружается.');
        return;
      }
      if (
        graph.getNodes().length > 0 &&
        !window.confirm(`Заменить текущий холст графом «${filename}»?`)
      ) {
        return;
      }

      setLoadingName(filename);
      setError(null);
      setMessage(null);
      try {
        const spec = await fetchSavedGraph(filename);
        const count = importMiaosToCanvas(graph, spec);
        setMessage(`Загружено на холст: ${filename} (${count} узлов)`);
        setStatus(`Graph Library → холст: ${filename}`);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Не удалось загрузить граф');
      } finally {
        setLoadingName(null);
      }
    },
    [graph],
  );

  return (
    <section className="miya-graph-library">
      <div className="miya-run-header">
        <h2 className="miya-run-title">Graph Library</h2>
        <span className="miya-run-badge">{items.length} graphs</span>
        <button
          type="button"
          className="miya-btn miya-btn-secondary"
          onClick={() => void refresh()}
          disabled={loading || saving}
        >
          {loading ? 'Загрузка…' : 'Обновить'}
        </button>
      </div>

      <p className="miya-run-hint">
        Каталог MiaOS-графов в <code>.miaos/graphs/</code> — <code>GET /graphs</code>, сохранение через{' '}
        <code>POST /graphs</code>.
      </p>

      <div className="miya-graph-save-row">
        <label className="miya-field miya-graph-save-field">
          <span>Имя файла</span>
          <input
            type="text"
            value={saveName}
            onChange={(e) => setSaveName(e.target.value)}
            placeholder="mia-minimal"
            disabled={saving}
          />
        </label>
        <button
          type="button"
          className="miya-btn miya-btn-primary"
          onClick={() => void saveCurrentGraph()}
          disabled={saving || !graph}
        >
          {saving ? 'Сохранение…' : 'Сохранить холст'}
        </button>
      </div>

      {message && <p className="miya-persona-message">{message}</p>}
      {error && <pre className="miya-run-error">{error}</pre>}

      {!loading && !error && items.length === 0 && (
        <p className="miya-run-hint">
          Библиотека пуста. Соберите граф на холсте (или **Шаблон Mia**) и нажмите **Сохранить холст**.
        </p>
      )}

      {items.length > 0 && (
        <div className="miya-model-table-wrap">
          <table className="miya-model-table">
            <thead>
              <tr>
                <th>Файл</th>
                <th>graph_id</th>
                <th>Название</th>
                <th>Узлы</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {items.map((item) => (
                <tr key={item.filename}>
                  <td>
                    <code>{item.filename}</code>
                  </td>
                  <td>{item.graph_id}</td>
                  <td>{item.name}</td>
                  <td>{item.node_count}</td>
                  <td>
                    <button
                      type="button"
                      className="miya-btn miya-btn-secondary"
                      onClick={() => void loadOntoCanvas(item.filename)}
                      disabled={loadingName === item.filename}
                    >
                      {loadingName === item.filename ? 'Загрузка…' : 'На холст'}
                    </button>
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
