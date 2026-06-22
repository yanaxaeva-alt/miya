import { useCallback, useEffect, useMemo, useState } from 'react';
import type { Graph } from '@antv/x6';
import { tryExportMiaosGraph } from './miaosExport';
import { validateMiaosGraphRemote } from './miaosApi';

interface GraphJsonPanelProps {
  graph: Graph | null;
}

export function GraphJsonPanel({ graph }: GraphJsonPanelProps) {
  const [validating, setValidating] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [refreshKey, setRefreshKey] = useState(0);

  useEffect(() => {
    if (!graph) return undefined;
    const bump = () => setRefreshKey((value) => value + 1);
    graph.on('cell:added', bump);
    graph.on('cell:removed', bump);
    graph.on('node:change:data', bump);
    graph.on('edge:connected', bump);
    return () => {
      graph.off('cell:added', bump);
      graph.off('cell:removed', bump);
      graph.off('node:change:data', bump);
      graph.off('edge:connected', bump);
    };
  }, [graph]);

  const preview = useMemo(() => {
    void refreshKey;
    if (!graph || graph.getNodes().length === 0) {
      return { json: '{\n  "hint": "Перетащите узлы на холст"\n}', warnings: [] as string[], exportError: null };
    }
    const result = tryExportMiaosGraph(graph);
    if ('error' in result) {
      return { json: '', warnings: [] as string[], exportError: result.error };
    }
    return {
      json: JSON.stringify(result.spec, null, 2),
      warnings: result.warnings,
      exportError: null,
    };
  }, [graph, refreshKey]);

  const copyJson = useCallback(async () => {
    if (!preview.json) return;
    try {
      await navigator.clipboard.writeText(preview.json);
      setMessage('JSON скопирован');
      setError(null);
    } catch {
      setError('Не удалось скопировать JSON');
    }
  }, [preview.json]);

  const validateRemote = useCallback(async () => {
    if (!graph) return;
    const result = tryExportMiaosGraph(graph);
    if ('error' in result) {
      setError(result.error);
      setMessage(null);
      return;
    }
    setValidating(true);
    setError(null);
    setMessage(null);
    try {
      const response = await validateMiaosGraphRemote(result.spec);
      setMessage(`Backend OK: ${response.name} (${response.graph_id})`);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Backend validation failed');
    } finally {
      setValidating(false);
    }
  }, [graph]);

  return (
    <div className="miya-graph-json-panel">
      <div className="miya-graph-json-actions">
        <button type="button" className="miya-btn miya-btn-secondary" onClick={() => void copyJson()} disabled={!preview.json}>
          Копировать JSON
        </button>
        <button
          type="button"
          className="miya-btn"
          onClick={() => void validateRemote()}
          disabled={validating || !graph}
        >
          {validating ? 'Проверка…' : 'Validate backend'}
        </button>
      </div>

      {preview.exportError && <pre className="miya-run-error">{preview.exportError}</pre>}
      {message && <p className="miya-persona-message">{message}</p>}
      {error && <pre className="miya-run-error">{error}</pre>}

      {preview.warnings.length > 0 && (
        <ul className="miya-graph-json-warnings">
          {preview.warnings.map((warning) => (
            <li key={warning}>{warning}</li>
          ))}
        </ul>
      )}

      <pre className="miya-graph-json-preview">{preview.json || preview.exportError || '{}'}</pre>
    </div>
  );
}
