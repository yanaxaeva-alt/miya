import type { Node } from '@antv/x6';
import { useEffect, useState } from 'react';

export function useNodeData<T extends Record<string, unknown> = Record<string, unknown>>(
  node: Node,
): T {
  const [data, setData] = useState<T>(() => (node.getData() as T) || ({} as T));

  useEffect(() => {
    const sync = () => {
      setData({ ...(node.getData() as T) });
    };
    node.on('change:data', sync);
    sync();
    return () => {
      node.off('change:data', sync);
    };
  }, [node]);

  return data;
}
