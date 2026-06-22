import type { Graph } from '@antv/x6';
import {
  downloadGraphJson,
  saveGraphToStorage,
  STORAGE_KEY,
} from './editor/graphStorage';
import { downloadMiaosGraph } from './editor/miaosExport';

let graph: Graph | null = null;

export function registerGraph(g: Graph | null) {
  graph = g;
}

export function setStatus(text: string) {
  const el = document.getElementById('miya-status');
  if (el) el.textContent = text;
}

function navigate(tab: string, target?: string) {
  window.dispatchEvent(new CustomEvent('miya:navigate', { detail: { tab, target } }));
}

export function setupToolbar() {
  const downloadBtn = document.getElementById('miya-download');
  const miaosBtn = document.getElementById('miya-miaos');
  const runBtn = document.getElementById('miya-run');
  const importBtn = document.getElementById('miya-import');
  const clearBtn = document.getElementById('miya-clear');
  const fileInput = document.getElementById('miya-file') as HTMLInputElement | null;

  downloadBtn?.addEventListener('click', () => {
    if (!graph) {
      navigate('graph', 'miya-graph-studio');
      setStatus('Открыл Graph Builder — холст загружается.');
      return;
    }
    if (graph.getNodes().length === 0) {
      window.alert('Сначала перетащите агента на серую область справа.');
      return;
    }
    downloadGraphJson(graph);
    setStatus(`X6 JSON: miya-graph.json (${new Date().toLocaleTimeString()})`);
  });

  miaosBtn?.addEventListener('click', () => {
    if (!graph) {
      navigate('graph', 'miya-graph-studio');
      setStatus('Открыл Graph Builder — холст загружается.');
      return;
    }

    try {
      const { spec, warnings } = downloadMiaosGraph(graph);
      const warnText = warnings.length ? ` (${warnings.length} авто-правок)` : '';
      setStatus(`MiaOS: ${spec.graph_id}.json${warnText}`);
      if (warnings.length) {
        window.alert(`Экспорт готов.\n\nАвто-правки:\n• ${warnings.join('\n• ')}`);
      }
    } catch (error) {
      window.alert(error instanceof Error ? error.message : 'Не удалось экспортировать граф.');
    }
  });

  runBtn?.addEventListener('click', () => {
    navigate('graph', 'miya-run-console');
    window.setTimeout(() => {
      window.dispatchEvent(new CustomEvent('miya:run-request'));
    }, 120);
  });

  importBtn?.addEventListener('click', () => {
    navigate('graph', 'miya-graph-studio');
    window.setTimeout(() => fileInput?.click(), 120);
  });

  fileInput?.addEventListener('change', () => {
    const file = fileInput.files?.[0];
    if (!file) return;
    if (!graph) {
      navigate('graph', 'miya-graph-studio');
      window.alert('Открыл Graph Builder. Повторите загрузку после инициализации холста.');
      fileInput.value = '';
      return;
    }

    const reader = new FileReader();
    reader.onload = () => {
      try {
        graph!.fromJSON(JSON.parse(reader.result as string));
        saveGraphToStorage(graph!);
        setStatus(`Загружено: ${file.name}`);
      } catch {
        window.alert('Не удалось прочитать JSON.');
      }
    };
    reader.readAsText(file);
    fileInput.value = '';
  });

  clearBtn?.addEventListener('click', () => {
    if (!graph) {
      navigate('graph', 'miya-graph-studio');
      setStatus('Открыл Graph Builder — холст загружается.');
      return;
    }
    if (!window.confirm('Очистить холст?')) return;
    graph.clearCells();
    localStorage.removeItem(STORAGE_KEY);
    setStatus('Холст очищен');
  });
}
