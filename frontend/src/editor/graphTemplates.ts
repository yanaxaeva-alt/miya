import type { Graph, Node } from '@antv/x6';

function addAgentNode(
  graph: Graph,
  name: string,
  model: string,
  role: string,
  x: number,
  y: number,
): Node {
  return graph.addNode({
    shape: 'agent-node',
    x,
    y,
    data: { name, model, status: 'idle', role },
    ports: [
      { id: 'p-in', group: 'in' },
      { id: 'p-out', group: 'out' },
    ],
  });
}

function connectOutToIn(graph: Graph, source: Node, target: Node) {
  graph.addEdge({
    source: { cell: source.id, port: 'p-out' },
    target: { cell: target.id, port: 'p-in' },
  });
}

/** Mia minimal approval pipeline: Planner → Worker → Approval. */
export function loadMiaMinimalTemplate(graph: Graph) {
  graph.clearCells();

  const planner = addAgentNode(graph, 'Планировщик', 'qwen3.5-8b', 'planner', 80, 120);
  const worker = addAgentNode(graph, 'Исполнитель', 'qwen3.5-coder-7b', 'executor', 320, 120);
  const approval = graph.addNode({
    shape: 'approval-node',
    x: 560,
    y: 120,
    data: { name: 'Согласование', action_class: 'publish' },
    ports: [
      { id: 'p-in', group: 'in' },
      { id: 'p-out', group: 'out' },
    ],
  });

  connectOutToIn(graph, planner, worker);
  connectOutToIn(graph, worker, approval);
}
