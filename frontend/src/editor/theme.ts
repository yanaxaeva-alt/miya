import type { Graph } from '@antv/x6';

export function readCssVar(name: string, fallback: string): string {
  const value = getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  return value || fallback;
}

export function readGraphTheme() {
  return {
    canvas: readCssVar('--bg-canvas', '#f5f5f5'),
    grid: readCssVar('--grid-color', '#dcdcdc'),
    edge: readCssVar('--edge-stroke', '#9ca3af'),
  };
}

export function applyGraphTheme(graph: Graph) {
  const { canvas, grid } = readGraphTheme();
  graph.drawBackground({ color: canvas });
  graph.drawGrid({
    type: 'mesh',
    args: { color: grid, thickness: 1 },
  });
}

export function watchSystemTheme(onChange: () => void): () => void {
  const media = window.matchMedia('(prefers-color-scheme: dark)');
  media.addEventListener('change', onChange);
  return () => media.removeEventListener('change', onChange);
}
