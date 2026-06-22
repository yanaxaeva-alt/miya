import type { Graph } from '@antv/x6';

export function countGraphNodes(graph: Graph): number {
  return graph
    .getNodes()
    .filter(
      (node) =>
        node.shape === 'agent-node' ||
        node.shape === 'approval-node' ||
        node.shape === 'tool-node' ||
        node.shape === 'io-node',
    ).length;
}

export function countGraphEdges(graph: Graph): number {
  return graph.getEdges().length;
}

export function nodeShapeLabel(shape: string | null): string {
  if (shape === 'agent-node') return 'agent';
  if (shape === 'approval-node') return 'approval';
  if (shape === 'tool-node') return 'tool';
  if (shape === 'io-node') return 'input/output';
  return 'node';
}
