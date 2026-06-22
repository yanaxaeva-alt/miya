import { useEffect, useState } from 'react';
import type { Graph, Node } from '@antv/x6';
import {
  AGENT_MODELS,
  AGENT_ROLES,
  AGENT_STATUSES,
  SANDBOX_TOOL_NAMES,
  type AgentNodeData,
  type ToolNodeData,
} from './agentTypes';
import { GraphJsonPanel } from './GraphJsonPanel';
import { nodeShapeLabel } from './graphStudioUtils';
import { resolveMiaosNodeId } from './miaosExport';
import type { MiaosGraphRun, MiaosModelRecord } from './miaosApi';

interface AgentInspectorProps {
  graph: Graph | null;
  nodeId: string | null;
  registeredModels?: MiaosModelRecord[];
  lastRun?: MiaosGraphRun | null;
}

interface ApprovalNodeData {
  name?: string;
  action_class?: string;
  active?: boolean;
}

interface IONodeData {
  name?: string;
  node_type?: 'input' | 'output';
  active?: boolean;
}

const ACTION_CLASSES = ['publish', 'delete', 'finance', 'self_modify'] as const;

function readInspectableNode(graph: Graph, nodeId: string): Node | null {
  const cell = graph.getCellById(nodeId);
  if (!cell?.isNode()) return null;
  if (
    cell.shape === 'agent-node' ||
    cell.shape === 'approval-node' ||
    cell.shape === 'tool-node' ||
    cell.shape === 'io-node'
  ) {
    return cell;
  }
  return null;
}

function InspectorRunOutput({
  graph,
  nodeId,
  lastRun,
}: {
  graph: Graph | null;
  nodeId: string;
  lastRun?: MiaosGraphRun | null;
}) {
  if (!graph || !lastRun) return null;
  const miaosId = resolveMiaosNodeId(graph, nodeId);
  if (!miaosId) return null;
  const output = lastRun.outputs[miaosId];
  if (!output) {
    return (
      <p className="miya-inspector-hint">
        Output появится после Run Console — MiaOS id: <code>{miaosId}</code>
      </p>
    );
  }

  return (
    <div className="miya-inspector-run-output">
      <h3 className="miya-inspector-subtitle">Output последнего run</h3>
      <p className="miya-inspector-id">
        <code>{miaosId}</code>
      </p>
      <pre>{output}</pre>
    </div>
  );
}

export function AgentInspector({
  graph,
  nodeId,
  registeredModels = [],
  lastRun = null,
}: AgentInspectorProps) {
  const [agentForm, setAgentForm] = useState<AgentNodeData | null>(null);
  const [approvalForm, setApprovalForm] = useState<ApprovalNodeData | null>(null);
  const [toolForm, setToolForm] = useState<ToolNodeData | null>(null);
  const [ioForm, setIoForm] = useState<IONodeData | null>(null);
  const [shape, setShape] = useState<string | null>(null);

  useEffect(() => {
    if (!graph || !nodeId) {
      setAgentForm(null);
      setApprovalForm(null);
      setToolForm(null);
      setIoForm(null);
      setShape(null);
      return;
    }

    const node = readInspectableNode(graph, nodeId);
    if (!node) {
      setAgentForm(null);
      setApprovalForm(null);
      setToolForm(null);
      setIoForm(null);
      setShape(null);
      return;
    }

    setShape(node.shape);

    const sync = () => {
      if (node.shape === 'approval-node') {
        setApprovalForm({ ...(node.getData() as ApprovalNodeData) });
        setAgentForm(null);
        setToolForm(null);
        setIoForm(null);
      } else if (node.shape === 'tool-node') {
        setToolForm({ ...(node.getData() as ToolNodeData) });
        setAgentForm(null);
        setApprovalForm(null);
        setIoForm(null);
      } else if (node.shape === 'io-node') {
        setIoForm({ ...(node.getData() as IONodeData) });
        setAgentForm(null);
        setApprovalForm(null);
        setToolForm(null);
      } else {
        setAgentForm({ ...(node.getData() as AgentNodeData) });
        setApprovalForm(null);
        setToolForm(null);
        setIoForm(null);
      }
    };

    sync();
    node.on('change:data', sync);
    return () => {
      node.off('change:data', sync);
    };
  }, [graph, nodeId]);

  const patchAgent = (patchData: Partial<AgentNodeData>) => {
    if (!graph || !nodeId) return;
    const node = readInspectableNode(graph, nodeId);
    if (!node || node.shape !== 'agent-node') return;
    node.setData({ ...(node.getData() as AgentNodeData), ...patchData });
  };

  const patchApproval = (patchData: Partial<ApprovalNodeData>) => {
    if (!graph || !nodeId) return;
    const node = readInspectableNode(graph, nodeId);
    if (!node || node.shape !== 'approval-node') return;
    node.setData({ ...(node.getData() as ApprovalNodeData), ...patchData });
  };

  const patchTool = (patchData: Partial<ToolNodeData>) => {
    if (!graph || !nodeId) return;
    const node = readInspectableNode(graph, nodeId);
    if (!node || node.shape !== 'tool-node') return;
    node.setData({ ...(node.getData() as ToolNodeData), ...patchData });
  };

  const patchIo = (patchData: Partial<IONodeData>) => {
    if (!graph || !nodeId) return;
    const node = readInspectableNode(graph, nodeId);
    if (!node || node.shape !== 'io-node') return;
    const nextData = { ...(node.getData() as IONodeData), ...patchData };
    node.setData(nextData);
    if (patchData.node_type) {
      node.prop(
        'ports/items',
        patchData.node_type === 'input'
          ? [{ id: 'p-out', group: 'out' }]
          : [{ id: 'p-in', group: 'in' }],
      );
    }
  };

  if (!nodeId || !shape) {
    return (
      <aside className="miya-inspector">
        <h2 className="miya-inspector-title">Inspector</h2>
        <p className="miya-inspector-hint">
          Выберите узел на холсте — agent, tool или approval — или смотрите MiaOS JSON ниже.
        </p>
        <GraphJsonPanel graph={graph} />
      </aside>
    );
  }

  if (shape === 'io-node' && ioForm) {
    return (
      <aside className="miya-inspector">
        <h2 className="miya-inspector-title">Inspector</h2>
        <p className="miya-inspector-id">
          {nodeShapeLabel(shape)} · {nodeId}
        </p>

        <label className="miya-field">
          <span>Название</span>
          <input
            type="text"
            value={ioForm.name ?? ''}
            onChange={(e) => patchIo({ name: e.target.value })}
          />
        </label>

        <label className="miya-field">
          <span>type</span>
          <select
            value={ioForm.node_type ?? 'input'}
            onChange={(e) => patchIo({ node_type: e.target.value as IONodeData['node_type'] })}
          >
            <option value="input">input / START</option>
            <option value="output">output / END</option>
          </select>
        </label>

        <InspectorRunOutput graph={graph} nodeId={nodeId} lastRun={lastRun} />
      </aside>
    );
  }

  if (shape === 'tool-node' && toolForm) {
    return (
      <aside className="miya-inspector">
        <h2 className="miya-inspector-title">Inspector</h2>
        <p className="miya-inspector-id">
          {nodeShapeLabel(shape)} · {nodeId}
        </p>

        <label className="miya-field">
          <span>Название</span>
          <input
            type="text"
            value={toolForm.name ?? ''}
            onChange={(e) => patchTool({ name: e.target.value })}
          />
        </label>

        <label className="miya-field">
          <span>tool_name</span>
          <select
            value={toolForm.tool_name ?? 'web_search_mock'}
            onChange={(e) => patchTool({ tool_name: e.target.value })}
          >
            {SANDBOX_TOOL_NAMES.map((value) => (
              <option key={value} value={value}>
                {value}
              </option>
            ))}
          </select>
        </label>

        <InspectorRunOutput graph={graph} nodeId={nodeId} lastRun={lastRun} />
      </aside>
    );
  }

  if (shape === 'approval-node' && approvalForm) {
    return (
      <aside className="miya-inspector">
        <h2 className="miya-inspector-title">Inspector</h2>
        <p className="miya-inspector-id">
          {nodeShapeLabel(shape)} · {nodeId}
        </p>

        <label className="miya-field">
          <span>Название</span>
          <input
            type="text"
            value={approvalForm.name ?? ''}
            onChange={(e) => patchApproval({ name: e.target.value })}
          />
        </label>

        <label className="miya-field">
          <span>action_class</span>
          <select
            value={approvalForm.action_class ?? 'publish'}
            onChange={(e) => patchApproval({ action_class: e.target.value })}
          >
            {ACTION_CLASSES.map((value) => (
              <option key={value} value={value}>
                {value}
              </option>
            ))}
          </select>
        </label>

        <InspectorRunOutput graph={graph} nodeId={nodeId} lastRun={lastRun} />
      </aside>
    );
  }

  if (!agentForm) {
    return null;
  }

  const modelOptions =
    registeredModels.length > 0
      ? registeredModels.map((model) => ({
          value: model.repo,
          label: `${model.repo} · ${model.quant} · ${model.status}`,
        }))
      : AGENT_MODELS.map((model) => ({ value: model, label: model }));

  const selectedModel = modelOptions.some((option) => option.value === agentForm.model)
    ? (agentForm.model ?? modelOptions[0]?.value)
    : modelOptions[0]?.value;

  return (
    <aside className="miya-inspector">
      <h2 className="miya-inspector-title">Inspector</h2>
      <p className="miya-inspector-id">
        {nodeShapeLabel(shape)} · {nodeId}
      </p>

      <label className="miya-field">
        <span>Имя</span>
        <input
          type="text"
          value={agentForm.name ?? ''}
          onChange={(e) => patchAgent({ name: e.target.value })}
        />
      </label>

      <label className="miya-field">
        <span>Модель</span>
        <select
          value={selectedModel ?? ''}
          onChange={(e) => patchAgent({ model: e.target.value })}
        >
          {modelOptions.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>
      </label>

      <label className="miya-field">
        <span>Роль</span>
        <select
          value={agentForm.role ?? 'planner'}
          onChange={(e) => patchAgent({ role: e.target.value })}
        >
          {AGENT_ROLES.map(({ value, label }) => (
            <option key={value} value={value}>
              {label}
            </option>
          ))}
        </select>
      </label>

      <label className="miya-field">
        <span>Статус (debug)</span>
        <select
          value={agentForm.status ?? 'idle'}
          onChange={(e) => patchAgent({ status: e.target.value as AgentNodeData['status'] })}
        >
          {AGENT_STATUSES.map(({ value, label }) => (
            <option key={value} value={value}>
              {label}
            </option>
          ))}
        </select>
      </label>

      <InspectorRunOutput graph={graph} nodeId={nodeId} lastRun={lastRun} />
    </aside>
  );
}
