import type { Edge, Graph, Node } from '@antv/x6';

export type MiaosNodeType = 'input' | 'llm' | 'critic' | 'approval' | 'output' | 'tool';

export interface MiaosNodeSpec {
  id: string;
  type: MiaosNodeType;
  label?: string;
  config?: Record<string, string | number | boolean>;
}

export interface MiaosEdgeSpec {
  source: string;
  target: string;
}

export interface MiaosGraphSpec {
  graph_id: string;
  name: string;
  nodes: MiaosNodeSpec[];
  edges: MiaosEdgeSpec[];
}

export interface MiaosExportResult {
  spec: MiaosGraphSpec;
  warnings: string[];
}

const START_ID = 'START';
const END_ID = 'END';

const ROLE_PROMPTS: Record<string, string> = {
  planner: 'You are a Qwen planning agent. Break the task into safe steps.',
  executor: 'You are a Qwen execution agent. Produce the final answer.',
  memory: 'You are a Qwen memory agent. Summarize and retain context.',
  perception: 'You are a Qwen perception agent. Parse and structure the input.',
  critic: 'You are a Qwen critic agent. Check the output for safety and quality issues.',
};

function slugifyId(name: string, fallback: string, used: Set<string>): string {
  let base =
    name
      .trim()
      .replace(/\s+/g, '_')
      .replace(/[^\w-]/g, '') || fallback;

  if (!/^[A-Za-z_]/.test(base)) {
    base = `N_${base}`;
  }

  let candidate = base;
  let suffix = 2;
  while (used.has(candidate)) {
    candidate = `${base}_${suffix}`;
    suffix += 1;
  }
  used.add(candidate);
  return candidate;
}

function getCanvasNodes(graph: Graph): Node[] {
  return graph.getNodes().filter(
    (node) =>
      node.shape === 'agent-node' ||
      node.shape === 'approval-node' ||
      node.shape === 'tool-node' ||
      node.shape === 'io-node',
  );
}

function getCanvasEdges(graph: Graph, nodeIds: Set<string>): Edge[] {
  return graph.getEdges().filter((edge) => {
    const sourceId = edge.getSourceCellId();
    const targetId = edge.getTargetCellId();
    return Boolean(sourceId && targetId && nodeIds.has(sourceId) && nodeIds.has(targetId));
  });
}

function nodeLabel(node: Node): string {
  const data = node.getData() || {};
  if (node.shape === 'approval-node') {
    return (data.name as string | undefined)?.trim() || 'Согласование';
  }
  if (node.shape === 'tool-node') {
    return (data.name as string | undefined)?.trim() || (data.tool_name as string | undefined) || 'Tool';
  }
  if (node.shape === 'io-node') {
    return (data.name as string | undefined)?.trim() || String(data.node_type ?? 'input').toUpperCase();
  }
  return (data.name as string | undefined)?.trim() || 'Безымянный агент';
}

function toMiaosNode(node: Node, id: string): MiaosNodeSpec {
  const data = node.getData() || {};
  const label = nodeLabel(node);

  if (node.shape === 'approval-node') {
    return {
      id,
      type: 'approval',
      label,
      config: { action_class: (data.action_class as string) || 'publish' },
    };
  }

  if (node.shape === 'io-node') {
    const nodeType = data.node_type === 'output' ? 'output' : 'input';
    return { id, type: nodeType, label };
  }

  if (node.shape === 'tool-node') {
    return {
      id,
      type: 'tool',
      label,
      config: { tool_name: (data.tool_name as string) || 'web_search_mock' },
    };
  }

  const role = (data.role as string) || 'executor';
  const config: Record<string, string | number | boolean> = {
    role,
    prompt: ROLE_PROMPTS[role] || 'Process the agent task.',
  };
  if (data.model) config.model = data.model as string;
  if (data.status) config.status = data.status as string;

  return { id, type: role === 'critic' ? 'critic' : 'llm', label, config };
}

function topologicalOrder(spec: MiaosGraphSpec): string[] {
  const nodeIds = new Set(spec.nodes.map((node) => node.id));
  const incoming = new Map<string, number>();
  const outgoing = new Map<string, string[]>();

  for (const id of nodeIds) {
    incoming.set(id, 0);
    outgoing.set(id, []);
  }

  for (const edge of spec.edges) {
    outgoing.get(edge.source)?.push(edge.target);
    incoming.set(edge.target, (incoming.get(edge.target) ?? 0) + 1);
  }

  const ready = [...nodeIds]
    .filter((id) => (incoming.get(id) ?? 0) === 0)
    .sort();
  const order: string[] = [];

  while (ready.length > 0) {
    const id = ready.shift()!;
    order.push(id);
    for (const target of outgoing.get(id) ?? []) {
      const next = (incoming.get(target) ?? 0) - 1;
      incoming.set(target, next);
      if (next === 0) {
        ready.push(target);
        ready.sort();
      }
    }
  }

  if (order.length !== nodeIds.size) {
    throw new Error('Граф содержит цикл — MiaOS принимает только DAG.');
  }

  return order;
}

export function validateMiaosGraph(spec: MiaosGraphSpec): string[] {
  const errors: string[] = [];
  const ids = spec.nodes.map((node) => node.id);

  if (ids.length !== new Set(ids).size) {
    errors.push('ID узлов должны быть уникальными.');
  }

  const idSet = new Set(ids);
  for (const edge of spec.edges) {
    if (!idSet.has(edge.source) || !idSet.has(edge.target)) {
      errors.push(`Ребро ссылается на неизвестный узел: ${edge.source} → ${edge.target}`);
    }
  }

  const types = new Set(spec.nodes.map((node) => node.type));
  if (!types.has('input')) {
    errors.push('В графе должен быть узел type=input (START).');
  }
  if (!types.has('output')) {
    errors.push('В графе должен быть узел type=output (END).');
  }

  if (errors.length === 0) {
    try {
      topologicalOrder(spec);
    } catch (error) {
      errors.push(error instanceof Error ? error.message : 'Граф не является DAG.');
    }
  }

  return errors;
}

function collectCanvasMiaosIds(graph: Graph): Map<string, Node> {
  const usedIds = new Set<string>();
  const map = new Map<string, Node>();

  for (const node of getCanvasNodes(graph)) {
    const data = node.getData() || {};
    const importedId = (data.miaos_id as string | undefined)?.trim();
    const preferred =
      node.shape === 'io-node' && data.node_type === 'input'
        ? START_ID
        : node.shape === 'io-node' && data.node_type === 'output'
          ? END_ID
          : importedId || nodeLabel(node);
    const id = slugifyId(preferred, node.id.slice(0, 8), usedIds);
    map.set(id, node);
  }

  return map;
}

export function buildMiaosNodeIdMap(graph: Graph): Map<string, Node> {
  return collectCanvasMiaosIds(graph);
}

export function resolveMiaosNodeId(graph: Graph, x6NodeId: string): string | null {
  const cell = graph.getCellById(x6NodeId);
  if (!cell?.isNode()) return null;
  if (
    cell.shape !== 'agent-node' &&
    cell.shape !== 'approval-node' &&
    cell.shape !== 'tool-node' &&
    cell.shape !== 'io-node'
  ) {
    return null;
  }
  for (const [miaosId, node] of collectCanvasMiaosIds(graph).entries()) {
    if (node.id === x6NodeId) return miaosId;
  }
  return null;
}

export function tryExportMiaosGraph(
  graph: Graph,
  options: { graphId?: string; name?: string } = {},
): MiaosExportResult | { error: string } {
  try {
    return exportToMiaosGraph(graph, options);
  } catch (error) {
    return { error: error instanceof Error ? error.message : 'Не удалось экспортировать граф' };
  }
}

export function exportToMiaosGraph(
  graph: Graph,
  options: { graphId?: string; name?: string } = {},
): MiaosExportResult {
  const canvasNodes = getCanvasNodes(graph);
  if (canvasNodes.length === 0) {
    throw new Error('На холсте нет узлов — перетащите агента или согласование.');
  }

  const warnings: string[] = [];
  const idMap = collectCanvasMiaosIds(graph);
  const x6ToMiaos = new Map<string, string>();
  for (const [miaosId, node] of idMap.entries()) {
    x6ToMiaos.set(node.id, miaosId);
  }

  const exportedNodes: MiaosNodeSpec[] = canvasNodes.map((node) => {
    const id = x6ToMiaos.get(node.id)!;
    return toMiaosNode(node, id);
  });

  const canvasIdSet = new Set(canvasNodes.map((node) => node.id));
  const edges: MiaosEdgeSpec[] = getCanvasEdges(graph, canvasIdSet).map((edge) => ({
    source: x6ToMiaos.get(edge.getSourceCellId()!)!,
    target: x6ToMiaos.get(edge.getTargetCellId()!)!,
  }));

  const targets = new Set(edges.map((edge) => edge.target));
  const sources = new Set(edges.map((edge) => edge.source));
  const hasInput = exportedNodes.some((node) => node.type === 'input');
  const hasOutput = exportedNodes.some((node) => node.type === 'output');

  for (const node of exportedNodes) {
    const id = node.id;
    if (node.type === 'input' || node.type === 'output') continue;
    if (!targets.has(id)) {
      edges.unshift({ source: START_ID, target: id });
      warnings.push(`У «${id}» нет входящих связей — добавлен START → ${id}.`);
    }
    if (!sources.has(id)) {
      edges.push({ source: id, target: END_ID });
      warnings.push(`У «${id}» нет исходящих связей — добавлен ${id} → END.`);
    }
  }

  const spec: MiaosGraphSpec = {
    graph_id: options.graphId || `miya-export-${Date.now()}`,
    name: options.name || 'Miya agent graph',
    nodes: [
      ...(hasInput ? [] : [{ id: START_ID, type: 'input' as const, label: 'Start' }]),
      ...exportedNodes,
      ...(hasOutput ? [] : [{ id: END_ID, type: 'output' as const, label: 'End' }]),
    ],
    edges,
  };

  const errors = validateMiaosGraph(spec);
  if (errors.length > 0) {
    throw new Error(errors.join('\n'));
  }

  return { spec, warnings };
}

export function downloadMiaosGraph(graph: Graph): MiaosExportResult {
  const result = exportToMiaosGraph(graph);
  const json = JSON.stringify(result.spec, null, 2);
  const blob = new Blob([json], { type: 'application/json;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = `${result.spec.graph_id}.json`;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(url);
  return result;
}
