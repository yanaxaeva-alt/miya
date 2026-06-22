import type { Node } from '@antv/x6';
import { register } from '@antv/x6-react-shape';
import { useNodeData } from './useNodeData';

function IOView({ node }: { node: Node }) {
  const data = useNodeData(node);
  const nodeType = (data.node_type as string | undefined) || 'input';
  const active = Boolean(data.active);
  const isInput = nodeType === 'input';

  return (
    <div
      style={{
        width: '100%',
        height: '100%',
        background: isInput ? 'var(--success-bg)' : 'var(--bg-subtle)',
        color: 'var(--text-h)',
        border: `2px solid ${isInput ? 'var(--success-border)' : 'var(--border-strong)'}`,
        borderRadius: 999,
        padding: '10px 12px',
        fontFamily: 'system-ui, -apple-system, sans-serif',
        boxShadow: active ? 'var(--node-active-shadow)' : 'var(--node-shadow)',
        boxSizing: 'border-box',
        textAlign: 'center',
        transition: 'box-shadow 0.2s ease, border-color 0.2s ease',
      }}
    >
      <div style={{ fontWeight: 700, fontSize: 13 }}>{(data.name as string) || 'START'}</div>
      <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 4 }}>
        type: {nodeType}
      </div>
    </div>
  );
}

register({
  shape: 'io-node',
  width: 150,
  height: 66,
  component: IOView,
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
