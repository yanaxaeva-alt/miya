import type { Node } from '@antv/x6';
import type { MiaosGraphEvent } from './miaosApi';

export function resetRunVisuals(idMap: Map<string, Node>) {
  for (const node of idMap.values()) {
    node.setData({ ...node.getData(), status: 'idle', active: false });
  }
}

export function applyRunEvent(idMap: Map<string, Node>, event: MiaosGraphEvent) {
  if (!event.node_id) {
    if (event.event_type === 'run_started') {
      resetRunVisuals(idMap);
    }
    return null;
  }

  const node = idMap.get(event.node_id);
  if (!node) return null;

  const data = { ...node.getData() };

  if (event.event_type === 'node_started') {
    for (const other of idMap.values()) {
      if (other.id !== node.id) {
        other.setData({
          ...other.getData(),
          active: false,
          status: 'idle',
        });
      }
    }
    node.setData({ ...data, status: 'running', active: true });
    return event.node_id;
  }

  if (event.event_type === 'node_completed') {
    node.setData({ ...data, status: 'idle', active: false });
    return null;
  }

  if (event.event_type === 'approval_required') {
    node.setData({ ...data, status: 'error', active: true });
    return event.node_id;
  }

  return null;
}

export function delay(ms: number) {
  return new Promise<void>((resolve) => {
    window.setTimeout(resolve, ms);
  });
}
