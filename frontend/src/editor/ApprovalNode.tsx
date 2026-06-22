import type { Node } from '@antv/x6';
import { register } from '@antv/x6-react-shape';
import { useNodeData } from './useNodeData';

function ApprovalView({ node }: { node: Node }) {
  const data = useNodeData(node);
  const actionClass = (data.action_class as string | undefined) || 'publish';
  const status = (data.status as string | undefined) || 'idle';
  const active = Boolean(data.active);

  return (
    <div
      style={{
        width: '100%',
        height: '100%',
        background: 'var(--approval-bg)',
        border: `2px solid ${status === 'error' ? 'var(--agent-error)' : 'var(--approval-border)'}`,
        borderRadius: 8,
        padding: 8,
        fontFamily: 'system-ui, -apple-system, sans-serif',
        boxSizing: 'border-box',
        boxShadow: active ? 'var(--approval-active-shadow)' : 'none',
        transition: 'box-shadow 0.2s ease, border-color 0.2s ease',
      }}
    >
      <div style={{ fontWeight: 700, fontSize: 13, color: 'var(--warning-text)' }}>
        {(data.name as string) || 'Согласование'}
      </div>
      <div style={{ fontSize: 11, color: 'var(--warning-accent)', marginTop: 4 }}>
        action: {actionClass}
      </div>
      {status !== 'idle' && (
        <div
          style={{
            fontSize: 11,
            color: status === 'error' ? 'var(--agent-error)' : 'var(--agent-running)',
            marginTop: 4,
          }}
        >
          ● {status}
        </div>
      )}
    </div>
  );
}

register({
  shape: 'approval-node',
  width: 180,
  height: 72,
  component: ApprovalView,
  ports: {
    groups: {
      in: {
        position: 'left',
        attrs: {
          circle: {
            r: 5,
            fill: 'var(--port-fill)',
            stroke: 'var(--approval-border)',
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
