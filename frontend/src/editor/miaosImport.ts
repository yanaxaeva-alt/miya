import type { Graph } from '@antv/x6';
import type { MiaosGraphSpec, MiaosNodeSpec } from './miaosExport';
import { saveGraphToStorage } from './graphStorage';

function isAgentNode(node: MiaosNodeSpec): boolean {
  return node.type === 'llm' || node.type === 'critic';
}

export function importMiaosToCanvas(graph: Graph, spec: MiaosGraphSpec): number {
  graph.clearCells();

  const canvasNodes = spec.nodes;
  const idToCell = new Map<string, ReturnType<Graph['addNode']>>();

  canvasNodes.forEach((node, index) => {
    const x = 80 + index * 240;
    const y = 120;

    if (node.type === 'input' || node.type === 'output') {
      const cell = graph.addNode({
        shape: 'io-node',
        x,
        y,
        data: {
          name: node.label || node.id,
          miaos_id: node.id,
          node_type: node.type,
        },
        ports:
          node.type === 'input'
            ? [{ id: 'p-out', group: 'out' }]
            : [{ id: 'p-in', group: 'in' }],
      });
      idToCell.set(node.id, cell);
      return;
    }

    if (node.type === 'approval') {
      const cell = graph.addNode({
        shape: 'approval-node',
        x,
        y,
        data: {
          name: node.label || node.id,
          miaos_id: node.id,
          action_class: String(node.config?.action_class ?? 'publish'),
        },
        ports: [
          { id: 'p-in', group: 'in' },
          { id: 'p-out', group: 'out' },
        ],
      });
      idToCell.set(node.id, cell);
      return;
    }

    if (node.type === 'tool') {
      const cell = graph.addNode({
        shape: 'tool-node',
        x,
        y,
        data: {
          name: node.label || node.id,
          miaos_id: node.id,
          tool_name: String(node.config?.tool_name ?? 'web_search_mock'),
          status: 'idle',
        },
        ports: [
          { id: 'p-in', group: 'in' },
          { id: 'p-out', group: 'out' },
        ],
      });
      idToCell.set(node.id, cell);
      return;
    }

    if (isAgentNode(node)) {
      const cell = graph.addNode({
        shape: 'agent-node',
        x,
        y,
        data: {
          name: node.label || node.id,
          miaos_id: node.id,
          model: String(node.config?.model ?? 'qwen3.5-8b'),
          role: String(node.config?.role ?? 'planner'),
          status: 'idle',
        },
        ports: [
          { id: 'p-in', group: 'in' },
          { id: 'p-out', group: 'out' },
        ],
      });
      idToCell.set(node.id, cell);
    }
  });

  for (const edge of spec.edges) {
    const source = idToCell.get(edge.source);
    const target = idToCell.get(edge.target);
    if (!source || !target) continue;
    graph.addEdge({
      source: { cell: source.id, port: 'p-out' },
      target: { cell: target.id, port: 'p-in' },
    });
  }

  saveGraphToStorage(graph);
  return canvasNodes.length;
}
