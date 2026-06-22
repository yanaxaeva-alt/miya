import { useEffect, useRef, useState } from 'react';
import {
  Clipboard,
  Graph,
  History,
  Keyboard,
  MiniMap,
  Selection,
  Snapline,
  Stencil,
  Transform,
  type Node,
} from '@antv/x6';
import './AgentNode';
import './ApprovalNode';
import './ToolNode';
import './IONode';
import { AgentInspector } from './AgentInspector';
import { countGraphEdges, countGraphNodes } from './graphStudioUtils';
import { loadGraphFromStorage, saveGraphToStorage } from './graphStorage';
import { registerGraph, setStatus } from '../miyaBridge';
import { applyGraphTheme, readCssVar, readGraphTheme, watchSystemTheme } from './theme';
import type { MiaosGraphRun, MiaosModelRecord } from './miaosApi';

export function SimpleGraph({
  onGraphReady,
  registeredModels = [],
  lastRun = null,
}: {
  onGraphReady?: (graph: Graph | null) => void;
  registeredModels?: MiaosModelRecord[];
  lastRun?: MiaosGraphRun | null;
}) {
  const containerRef = useRef<HTMLDivElement>(null);
  const minimapRef = useRef<HTMLDivElement>(null);
  const stencilRef = useRef<HTMLDivElement>(null);
  const [graphInstance, setGraphInstance] = useState<Graph | null>(null);
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const [nodeCount, setNodeCount] = useState(0);
  const [edgeCount, setEdgeCount] = useState(0);
  const [canUndo, setCanUndo] = useState(false);
  const [canRedo, setCanRedo] = useState(false);

  useEffect(() => {
    if (!containerRef.current || !stencilRef.current || !minimapRef.current) return;

    const canvasEl = containerRef.current;
    const initialTheme = readGraphTheme();
    const graph: Graph = new Graph({
      container: canvasEl,
      autoResize: canvasEl,
      background: { color: initialTheme.canvas },
      grid: {
        visible: true,
        size: 10,
        type: 'mesh',
        args: { color: initialTheme.grid, thickness: 1 },
      },
      panning: { enabled: true, modifiers: ['ctrl'] },
      mousewheel: { enabled: true, modifiers: ['ctrl'] },
      connecting: {
        snap: true,
        allowBlank: false,
        allowLoop: false,
        allowNode: false,
        allowPort: true,
        highlight: true,
        router: { name: 'manhattan' },
        connector: { name: 'rounded', args: { radius: 8 } },
        validateConnection: ({ sourceMagnet, targetMagnet }) => {
          if (!sourceMagnet || !targetMagnet) return false;
          const sourceGroup = sourceMagnet.getAttribute('port-group');
          const targetGroup = targetMagnet.getAttribute('port-group');
          return sourceGroup === 'out' && targetGroup === 'in';
        },
        createEdge() {
          return graph.createEdge({
            attrs: {
              line: {
                stroke: readCssVar('--edge-stroke', '#9ca3af'),
                strokeWidth: 2,
                targetMarker: {
                  name: 'classic',
                  size: 8,
                },
              },
            },
          });
        },
      },
    });

    applyGraphTheme(graph);
    const stopThemeWatch = watchSystemTheme(() => {
      applyGraphTheme(graph);
      graph.getEdges().forEach((edge) => {
        edge.attr('line/stroke', readCssVar('--edge-stroke', '#9ca3af'));
      });
    });

    setGraphInstance(graph);
    onGraphReady?.(graph);
    registerGraph(graph);

    const transform = new Transform({
      resizing: {
        enabled: (node) =>
          node.shape === 'agent-node' ||
          node.shape === 'approval-node' ||
          node.shape === 'tool-node',
        minWidth: 140,
        minHeight: 60,
        maxWidth: 320,
        maxHeight: 160,
        preserveAspectRatio: false,
      },
      rotating: {
        enabled: () => false,
      },
    });

    graph
      .use(new Snapline({ enabled: true, sharp: true }))
      .use(
        new Selection({
          enabled: true,
          multiple: true,
          rubberband: true,
          showNodeSelectionBox: true,
        }),
      )
      .use(new Keyboard({ enabled: true }))
      .use(new History({ enabled: true }))
      .use(new Clipboard({ enabled: true }))
      .use(transform)
      .use(
        new MiniMap({
          container: minimapRef.current,
          width: 200,
          height: 140,
          padding: 8,
          scalable: true,
        }),
      );

    graph.bindKey(['ctrl+z', 'meta+z'], () => {
      if (graph.canUndo()) graph.undo();
    });
    graph.bindKey(['ctrl+shift+z', 'meta+shift+z', 'ctrl+y'], () => {
      if (graph.canRedo()) graph.redo();
    });
    graph.bindKey(['ctrl+c', 'meta+c'], () => {
      const cells = graph.getSelectedCells();
      if (cells.length) graph.copy(cells);
    });
    graph.bindKey(['ctrl+v', 'meta+v'], () => {
      if (!graph.isClipboardEmpty()) {
        const cells = graph.paste({ offset: 32 });
        graph.cleanSelection();
        graph.select(cells);
      }
    });
    graph.bindKey(['delete', 'backspace'], () => {
      const cells = graph.getSelectedCells();
      if (cells.length) graph.removeCells(cells);
    });

    const syncStats = () => {
      setNodeCount(countGraphNodes(graph));
      setEdgeCount(countGraphEdges(graph));
    };

    const syncHistory = () => {
      setCanUndo(graph.canUndo());
      setCanRedo(graph.canRedo());
    };

    const persist = () => {
      try {
        saveGraphToStorage(graph);
        setStatus(`Автосохранено ${new Date().toLocaleTimeString()}`);
        syncStats();
      } catch {
        setStatus('Не удалось сохранить');
      }
    };

    const syncSelection = () => {
      const selected = graph
        .getSelectedCells()
        .find(
          (cell) =>
            cell.isNode() &&
            (cell.shape === 'agent-node' ||
              cell.shape === 'approval-node' ||
              cell.shape === 'tool-node'),
        );
      setSelectedNodeId(selected?.id ?? null);

      if (selected?.isNode()) {
        transform.createWidget(selected as Node);
      } else if (graph.getSelectedCells().length === 0) {
        transform.clearWidgets();
      }
    };

    graph.on('selection:changed', syncSelection);
    graph.on('history:change', syncHistory);
    graph.on('cell:added', persist);
    graph.on('node:added', persist);
    graph.on('edge:added', persist);
    graph.on('node:removed', persist);
    graph.on('edge:removed', persist);
    graph.on('node:change:position', persist);
    graph.on('node:change:size', persist);
    graph.on('node:change:data', persist);
    graph.on('edge:change:vertices', persist);
    graph.on('edge:connected', persist);

    const stencil = new Stencil({
      title: 'Палитра узлов',
      target: graph,
      search: {
        'agent-node': ['data/name', 'data/model', 'data/role'],
        'approval-node': ['data/name', 'data/action_class'],
        'tool-node': ['data/name', 'data/tool_name'],
        'io-node': ['data/name', 'data/node_type'],
      },
      placeholder: 'Поиск узла…',
      notFoundText: 'Ничего не найдено',
      collapsable: true,
      stencilGraphWidth: 240,
      stencilGraphHeight: 0,
      stencilGraphPadding: 12,
      layoutOptions: {
        columns: 1,
        columnWidth: 200,
        rowHeight: 82,
        marginX: 12,
        marginY: 8,
        dx: 8,
        dy: 8,
      },
      groups: [
        { name: 'io', title: 'Input / Output' },
        { name: 'tools', title: 'Tools: Web search / Draft', graphHeight: 360 },
        { name: 'planning', title: 'Планирование' },
        { name: 'execution', title: 'Исполнение' },
        { name: 'memory', title: 'Память' },
        { name: 'perception', title: 'Восприятие' },
        { name: 'safety', title: 'Безопасность' },
      ],
    });

    stencilRef.current.replaceChildren();
    stencilRef.current.appendChild(stencil.container);

    const makeTemplate = (name: string, model: string, role: string) =>
      graph.createNode({
        shape: 'agent-node',
        data: { name, model, status: 'idle', role },
        ports: [
          { id: 'p-in', group: 'in' },
          { id: 'p-out', group: 'out' },
        ],
      });

    const makeIoTemplate = (name: string, nodeType: 'input' | 'output') =>
      graph.createNode({
        shape: 'io-node',
        data: { name, node_type: nodeType },
        ports:
          nodeType === 'input'
            ? [{ id: 'p-out', group: 'out' }]
            : [{ id: 'p-in', group: 'in' }],
      });

    const makeToolTemplate = (name: string, toolName: string) =>
      graph.createNode({
        shape: 'tool-node',
        data: { name, tool_name: toolName, status: 'idle' },
        ports: [
          { id: 'p-in', group: 'in' },
          { id: 'p-out', group: 'out' },
        ],
      });

    stencil.load([makeIoTemplate('START', 'input'), makeIoTemplate('END', 'output')], 'io');
    stencil.load(
      [
        makeToolTemplate('Web search', 'web_search_mock'),
        makeToolTemplate('Draft', 'create_draft'),
        makeToolTemplate('Read file', 'read_file_sandbox'),
        makeToolTemplate('Write file', 'write_file_sandbox'),
      ],
      'tools',
    );
    stencil.load([makeTemplate('Планировщик', 'qwen3.5-8b', 'planner')], 'planning');
    stencil.load(
      [
        makeTemplate('Исполнитель', 'qwen3.5-coder-7b', 'executor'),
        makeTemplate('Критик', 'qwen3.5-8b', 'critic'),
      ],
      'execution',
    );
    stencil.load([makeTemplate('Память', 'qwen3.5-4b', 'memory')], 'memory');
    stencil.load([makeTemplate('Восприятие', 'qwen3.5-4b', 'perception')], 'perception');
    stencil.load(
      [
        graph.createNode({
          shape: 'approval-node',
          data: { name: 'Согласование', action_class: 'publish' },
          ports: [
            { id: 'p-in', group: 'in' },
            { id: 'p-out', group: 'out' },
          ],
        }),
      ],
      'safety',
    );

    syncStats();
    syncHistory();

    if (loadGraphFromStorage(graph)) {
      setStatus('Граф восстановлен из localStorage');
    } else {
      setStatus('Перетащите агента на холст → кликните → тяните углы');
    }

    return () => {
      stopThemeWatch();
      graph.off('selection:changed', syncSelection);
      graph.off('history:change', syncHistory);
      graph.off('cell:added', persist);
      graph.off('node:added', persist);
      graph.off('edge:added', persist);
      graph.off('node:removed', persist);
      graph.off('edge:removed', persist);
      graph.off('node:change:position', persist);
      graph.off('node:change:size', persist);
      graph.off('node:change:data', persist);
      graph.off('edge:change:vertices', persist);
      graph.off('edge:connected', persist);
      setGraphInstance(null);
      onGraphReady?.(null);
      registerGraph(null);
      setSelectedNodeId(null);
      stencil.dispose();
      graph.dispose();
    };
  }, [onGraphReady]);

  const fitCanvas = () => {
    if (!graphInstance) return;
    graphInstance.zoomToFit({ padding: 40, maxScale: 1 });
    setStatus('Холст: fit to view');
  };

  const undo = () => {
    if (!graphInstance?.canUndo()) return;
    graphInstance.undo();
    setStatus('Undo');
  };

  const redo = () => {
    if (!graphInstance?.canRedo()) return;
    graphInstance.redo();
    setStatus('Redo');
  };

  return (
    <section id="miya-graph-studio" className="miya-graph-studio">
      <div className="miya-run-header">
        <h2 className="miya-run-title">Graph Studio</h2>
        <span className="miya-run-badge">{nodeCount} узлов</span>
        <span className="miya-run-badge">{edgeCount} связей</span>
      </div>

      <div className="miya-graph-chrome">
        <div className="miya-graph-chrome-actions">
          <button type="button" className="miya-btn" onClick={fitCanvas} disabled={!graphInstance}>
            Fit view
          </button>
          <button type="button" className="miya-btn" onClick={undo} disabled={!canUndo}>
            Undo
          </button>
          <button type="button" className="miya-btn" onClick={redo} disabled={!canRedo}>
            Redo
          </button>
        </div>
        <p className="miya-graph-chrome-hint">
          Ctrl+колёсико — zoom · Ctrl+drag — pan · порты out→in · Inspector справа — JSON и output
        </p>
      </div>

      <div className="miya-workspace">
      <div className="miya-canvas-wrap">
        <div ref={stencilRef} className="miya-stencil" />
        <div className="miya-canvas-host">
          <div ref={containerRef} className="miya-canvas" />
          <div ref={minimapRef} className="miya-minimap" aria-label="Minimap" />
        </div>
      </div>
      <AgentInspector
        graph={graphInstance}
        nodeId={selectedNodeId}
        registeredModels={registeredModels}
        lastRun={lastRun}
      />
      </div>
    </section>
  );
}
