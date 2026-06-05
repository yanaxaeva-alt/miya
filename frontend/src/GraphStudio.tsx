import {
  Background,
  Controls,
  Handle,
  MarkerType,
  MiniMap,
  Position,
  ReactFlow,
  ReactFlowProvider,
  addEdge,
  applyEdgeChanges,
  applyNodeChanges,
  type Connection,
  type Edge,
  type EdgeChange,
  type Node,
  type NodeChange,
  type NodeProps,
} from '@xyflow/react'
import '@xyflow/react/dist/style.css'
import './GraphStudio.css'
import { useCallback, useEffect, useMemo, useState } from 'react'

const graphNodeTypes = ['input', 'llm', 'tool', 'memory', 'critic', 'approval', 'output'] as const
const dangerousActionClasses = new Set([
  'financial_transaction',
  'self_modification',
  'contract_bypass',
  'disable_guardrails',
  'bypass_kill_switch',
  'publish',
  'send_message',
  'delete',
  'write_outside_sandbox',
])

type GraphNodeType = (typeof graphNodeTypes)[number]
type ConfigValue = string | number | boolean
type GraphConfig = Record<string, ConfigValue>

type StudioNodeData = {
  label: string
  type: GraphNodeType
  config: GraphConfig
  active?: boolean
  output?: string
}

type StudioNode = Node<StudioNodeData>

type GraphSpec = {
  graph_id: string
  name: string
  nodes: Array<{
    id: string
    type: GraphNodeType
    label?: string
    config?: GraphConfig
  }>
  edges: Array<{ source: string; target: string }>
}

type GraphEvent = {
  event_type: string
  node_id?: string | null
  message: string
  payload?: Record<string, ConfigValue>
}

type GraphStudioProps = {
  apiBaseUrl: string
}

const initialNodes: StudioNode[] = [
  {
    id: 'START',
    position: { x: 0, y: 80 },
    type: 'studioNode',
    data: { label: 'Start', type: 'input', config: {} },
  },
  {
    id: 'Planner',
    position: { x: 260, y: 40 },
    type: 'studioNode',
    data: { label: 'Planner', type: 'llm', config: { prompt: 'Plan a safe response.' } },
  },
  {
    id: 'Approval',
    position: { x: 520, y: 40 },
    type: 'studioNode',
    data: { label: 'Approval', type: 'approval', config: { action_class: 'publish' } },
  },
  {
    id: 'END',
    position: { x: 780, y: 80 },
    type: 'studioNode',
    data: { label: 'End', type: 'output', config: {} },
  },
]

const initialEdges: Edge[] = [
  { id: 'START-Planner', source: 'START', target: 'Planner', markerEnd: { type: MarkerType.Arrow } },
  {
    id: 'Planner-Approval',
    source: 'Planner',
    target: 'Approval',
    markerEnd: { type: MarkerType.Arrow },
  },
  { id: 'Approval-END', source: 'Approval', target: 'END', markerEnd: { type: MarkerType.Arrow } },
]

function GraphStudio({ apiBaseUrl }: GraphStudioProps) {
  const [nodes, setNodes] = useState<StudioNode[]>(initialNodes)
  const [edges, setEdges] = useState<Edge[]>(initialEdges)
  const [selectedNodeId, setSelectedNodeId] = useState<string>('Planner')
  const [configText, setConfigText] = useState<string>(JSON.stringify(initialNodes[1].data.config, null, 2))
  const [graphName, setGraphName] = useState<string>('studio-graph.json')
  const [savedGraphs, setSavedGraphs] = useState<string[]>([])
  const [validationMessage, setValidationMessage] = useState<string>('Not validated yet.')
  const [runInput, setRunInput] = useState<string>('Draft a safe post')
  const [events, setEvents] = useState<GraphEvent[]>([])

  const selectedNode = nodes.find((node) => node.id === selectedNodeId) ?? null
  const graphSpec = useMemo(() => toGraphSpec(nodes, edges), [nodes, edges])

  useEffect(() => {
    void refreshSavedGraphs(apiBaseUrl, setSavedGraphs)
  }, [apiBaseUrl])

  const onNodesChange = useCallback((changes: NodeChange<StudioNode>[]) => {
    setNodes((currentNodes) => applyNodeChanges(changes, currentNodes))
  }, [])
  const onEdgesChange = useCallback((changes: EdgeChange<Edge>[]) => {
    setEdges((currentEdges) => applyEdgeChanges(changes, currentEdges))
  }, [])
  const onConnect = useCallback((connection: Connection) => {
    setEdges((currentEdges) =>
      addEdge({ ...connection, markerEnd: { type: MarkerType.Arrow } }, currentEdges),
    )
  }, [])

  function addNode(type: GraphNodeType) {
    const id = `${type}_${nodes.length + 1}`
    const config = defaultConfigForType(type)
    setNodes((currentNodes) => [
      ...currentNodes,
      {
        id,
        position: { x: 120 + currentNodes.length * 36, y: 220 },
        type: 'studioNode',
        data: {
          label: labelForType(type),
          type,
          config,
        },
      },
    ])
    setSelectedNodeId(id)
    setConfigText(JSON.stringify(config, null, 2))
  }

  function selectNode(node: StudioNode) {
    setSelectedNodeId(node.id)
    setConfigText(JSON.stringify(node.data.config, null, 2))
  }

  function updateSelectedNode(next: Partial<StudioNodeData>) {
    setNodes((currentNodes) =>
      currentNodes.map((node) =>
        node.id === selectedNodeId ? { ...node, data: { ...node.data, ...next } } : node,
      ),
    )
  }

  function saveConfig() {
    try {
      const parsed = JSON.parse(configText) as GraphConfig
      updateSelectedNode({ config: parsed })
      setValidationMessage('Node config updated.')
    } catch (error) {
      setValidationMessage(`Invalid node config JSON: ${String(error)}`)
    }
  }

  async function validateGraph() {
    const response = await fetch(`${apiBaseUrl}/graphs/validate`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ graph: graphSpec }),
    })
    const body = (await response.json()) as { valid?: boolean; detail?: string }
    setValidationMessage(response.ok ? `Valid graph: ${body.valid}` : `Invalid graph: ${body.detail}`)
  }

  async function saveGraph() {
    const response = await fetch(`${apiBaseUrl}/graphs/${encodeURIComponent(graphName)}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ graph: graphSpec }),
    })
    const body = (await response.json()) as { saved?: boolean; detail?: string }
    setValidationMessage(response.ok ? `Saved: ${body.saved}` : `Save failed: ${body.detail}`)
    await refreshSavedGraphs(apiBaseUrl, setSavedGraphs)
  }

  async function loadGraph(name: string) {
    const response = await fetch(`${apiBaseUrl}/graphs/${encodeURIComponent(name)}`)
    if (!response.ok) {
      setValidationMessage(`Load failed: ${response.status}`)
      return
    }
    const spec = (await response.json()) as GraphSpec
    setGraphName(name)
    setNodes(fromGraphSpecNodes(spec))
    setEdges(fromGraphSpecEdges(spec))
    setSelectedNodeId(spec.nodes[0]?.id ?? '')
    setConfigText(JSON.stringify(spec.nodes[0]?.config ?? {}, null, 2))
    setEvents([])
    setValidationMessage(`Loaded: ${name}`)
  }

  async function runGraph() {
    const runId = `run_${crypto.randomUUID().replaceAll('-', '')}`
    const websocketUrl = `${apiBaseUrl.replace(/^http/, 'ws')}/runs/${runId}/events`
    setEvents([])
    setNodes((currentNodes) =>
      currentNodes.map((node) => ({ ...node, data: { ...node.data, active: false, output: '' } })),
    )
    const websocket = new WebSocket(websocketUrl)
    websocket.onmessage = (message) => {
      const event = JSON.parse(message.data as string) as GraphEvent
      setEvents((currentEvents) => [...currentEvents, event])
      if (event.node_id) {
        setNodes((currentNodes) =>
          currentNodes.map((node) => ({
            ...node,
            data: {
              ...node.data,
              active: node.id === event.node_id,
              output:
                node.id === event.node_id && event.payload?.output
                  ? String(event.payload.output)
                  : node.data.output,
            },
          })),
        )
      }
    }
    await new Promise<void>((resolve) => {
      websocket.onopen = () => resolve()
    })
    const response = await fetch(`${apiBaseUrl}/graphs/run`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ graph: graphSpec, input_text: runInput, run_id: runId }),
    })
    setValidationMessage(response.ok ? `Mock run started: ${runId}` : `Mock run failed: ${response.status}`)
  }

  return (
    <section className="graph-studio">
      <div className="graph-toolbar">
        <div className="node-palette">
          {graphNodeTypes.map((type) => (
            <button key={type} onClick={() => addNode(type)} type="button">
              + {type}
            </button>
          ))}
        </div>
        <div className="graph-actions">
          <input onChange={(event) => setGraphName(event.target.value)} value={graphName} />
          <button onClick={validateGraph} type="button">
            Validate
          </button>
          <button onClick={saveGraph} type="button">
            Save
          </button>
          <button onClick={runGraph} type="button">
            Mock-run
          </button>
        </div>
      </div>

      <div className="graph-layout">
        <ReactFlowProvider>
          <div className="graph-canvas">
            <ReactFlow
              edges={edges}
              fitView
              nodeTypes={{ studioNode: StudioNodeCard }}
              nodes={nodes}
              onConnect={onConnect}
              onEdgesChange={onEdgesChange}
              onNodeClick={(_event, node) => selectNode(node)}
              onNodesChange={onNodesChange}
            >
              <Background />
              <MiniMap />
              <Controls />
            </ReactFlow>
          </div>
        </ReactFlowProvider>

        <aside className="graph-inspector">
          <h2>Inspector</h2>
          {selectedNode ? (
            <>
              <label>
                Label
                <input
                  onChange={(event) => updateSelectedNode({ label: event.target.value })}
                  value={selectedNode.data.label}
                />
              </label>
              <label>
                Type
                <select
                  onChange={(event) => {
                    const nextType = event.target.value as GraphNodeType
                    const nextConfig = defaultConfigForType(nextType)
                    updateSelectedNode({
                      type: nextType,
                      config: nextConfig,
                    })
                    setConfigText(JSON.stringify(nextConfig, null, 2))
                  }}
                  value={selectedNode.data.type}
                >
                  {graphNodeTypes.map((type) => (
                    <option key={type} value={type}>
                      {type}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                Config JSON
                <textarea onChange={(event) => setConfigText(event.target.value)} value={configText} />
              </label>
              <button onClick={saveConfig} type="button">
                Apply node config
              </button>
              {isDangerousNode(selectedNode.data) ? <span className="blocked-badge">blocked</span> : null}
            </>
          ) : (
            <p>Select a node to inspect it.</p>
          )}
          <h2>Saved graphs</h2>
          {savedGraphs.map((name) => (
            <button className="saved-graph" key={name} onClick={() => void loadGraph(name)} type="button">
              {name}
            </button>
          ))}
          <h2>Run input</h2>
          <textarea onChange={(event) => setRunInput(event.target.value)} value={runInput} />
        </aside>
      </div>

      <div className="graph-bottom">
        <article>
          <h2>Validation</h2>
          <p>{validationMessage}</p>
        </article>
        <article>
          <h2>Live events</h2>
          <div className="event-log">
            {events.map((event, index) => (
              <div key={`${event.event_type}-${index}`}>
                <strong>{event.event_type}</strong>
                <span>{event.node_id ?? 'run'}</span>
                <small>{event.message}</small>
              </div>
            ))}
          </div>
        </article>
        <article>
          <h2>Graph JSON</h2>
          <pre>{JSON.stringify(graphSpec, null, 2)}</pre>
        </article>
      </div>
    </section>
  )
}

function StudioNodeCard({ data }: NodeProps<StudioNode>) {
  return (
    <div className={data.active ? 'studio-node active' : 'studio-node'}>
      <Handle position={Position.Left} type="target" />
      <div>
        <strong>{data.label}</strong>
        <small>{data.type}</small>
      </div>
      {isDangerousNode(data) ? <span className="blocked-badge">blocked</span> : null}
      {data.output ? <p>{data.output}</p> : null}
      <Handle position={Position.Right} type="source" />
    </div>
  )
}

function toGraphSpec(nodes: StudioNode[], edges: Edge[]): GraphSpec {
  return {
    graph_id: 'studio-graph',
    name: 'Graph Studio graph',
    nodes: nodes.map((node) => ({
      id: node.id,
      type: node.data.type,
      label: node.data.label,
      config: node.data.config,
    })),
    edges: edges
      .filter((edge) => edge.source && edge.target)
      .map((edge) => ({ source: edge.source, target: edge.target })),
  }
}

function fromGraphSpecNodes(spec: GraphSpec): StudioNode[] {
  return spec.nodes.map((node, index) => ({
    id: node.id,
    position: { x: index * 220, y: 80 + (index % 2) * 120 },
    type: 'studioNode',
    data: {
      label: node.label ?? node.id,
      type: node.type,
      config: node.config ?? {},
    },
  }))
}

function fromGraphSpecEdges(spec: GraphSpec): Edge[] {
  return spec.edges.map((edge) => ({
    id: `${edge.source}-${edge.target}`,
    source: edge.source,
    target: edge.target,
    markerEnd: { type: MarkerType.Arrow },
  }))
}

function defaultConfigForType(type: GraphNodeType): GraphConfig {
  if (type === 'llm') {
    return { prompt: 'Process this input safely.' }
  }
  if (type === 'tool') {
    return { tool_name: 'web_search_mock', action_class: 'read' }
  }
  if (type === 'approval') {
    return { action_class: 'publish' }
  }
  if (type === 'memory') {
    return { mode: 'mock_read' }
  }
  return {}
}

function labelForType(type: GraphNodeType): string {
  return type
    .split('_')
    .map((part) => `${part[0]?.toUpperCase() ?? ''}${part.slice(1)}`)
    .join(' ')
}

function isDangerousNode(data: StudioNodeData): boolean {
  const actionClass = data.config.action_class
  return typeof actionClass === 'string' && dangerousActionClasses.has(actionClass)
}

async function refreshSavedGraphs(
  apiBaseUrl: string,
  setSavedGraphs: (graphs: string[]) => void,
) {
  try {
    const response = await fetch(`${apiBaseUrl}/graphs`)
    if (!response.ok) {
      return
    }
    setSavedGraphs((await response.json()) as string[])
  } catch {
    setSavedGraphs([])
  }
}

export default GraphStudio
