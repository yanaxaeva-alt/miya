import type { Node } from '@antv/x6';
import { register } from '@antv/x6-react-shape';
import { useNodeData } from './useNodeData';

function ToolView({ node }: { node: Node }) {
  const data = useNodeData(node);
  const status = (data.status as string | undefined) || 'idle';
  const active = Boolean(data.active);
  const toolName = (data.tool_name as string | undefined) || 'web_search_mock';

  const statusColor: Record<string, string> = {
    idle: 'var(--agent-idle)',
    running: 'var(--agent-running)',
    error: 'var(--agent-error)',
  };

  return (
    <div
      style={{
        width: '100%',
        height: '100%',
        background: 'var(--info-bg)',
        color: 'var(--text-h)',
        border: `2px solid ${statusColor[status] ?? 'var(--info-border)'}`,
        borderRadius: 8,
        padding: 8,
        fontFamily: 'system-ui, -apple-system, sans-serif',
        boxShadow: active ? 'var(--node-active-shadow)' : 'var(--node-shadow)',
        boxSizing: 'border-box',
        transition: 'box-shadow 0.2s ease, border-color 0.2s ease',
      }}
    >
      <div style={{ fontWeight: 700, fontSize: 13, color: 'var(--info-text)' }}>
        {(data.name as string) || 'Tool'}
      </div>
      <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 4 }}>
        tool: <code style={{ fontSize: 10 }}>{toolName}</code>
      </div>
      <div style={{ fontSize: 11, color: statusColor[status] ?? statusColor.idle, marginTop: 4 }}>
        ● {status}
      </div>
    </div>
  );
}

register({
  shape: 'tool-node',
  width: 180,
  height: 80,
  component: ToolView,
  ports: {
    groups: {
      in: {
        position: 'left',
        attrs: {
          circle: {
            r: 5,
            fill: 'var(--port-fill)',
            stroke: 'var(--port-in)',
            strokeWidth: 2,
            magnet: true,
          },
        },
      },
      out: {
        position: 'right',
        attrs: {
          circle: {
            r: 5,
            fill: 'var(--port-fill)',
            stroke: 'var(--port-out)',
            strokeWidth: 2,
            magnet: true,
          },
        },
      },
    },
  },
});
