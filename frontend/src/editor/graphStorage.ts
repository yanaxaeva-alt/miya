import type { Graph } from '@antv/x6';

export const STORAGE_KEY = 'miya-graph';

export function saveGraphToStorage(graph: Graph) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(graph.toJSON()));
}

export function loadGraphFromStorage(graph: Graph) {
  const saved = localStorage.getItem(STORAGE_KEY);
  if (!saved) return false;

  try {
    const data = JSON.parse(saved);
    if (data.cells?.length) {
      graph.fromJSON(data);
      return true;
    }
  } catch {
    localStorage.removeItem(STORAGE_KEY);
  }
  return false;
}

export function downloadGraphJson(graph: Graph) {
  const json = JSON.stringify(graph.toJSON(), null, 2);
  const blob = new Blob([json], { type: 'application/json;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = 'miya-graph.json';
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(url);
}
