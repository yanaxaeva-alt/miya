import type { Graph } from '@antv/x6';
import type { MiaosGraphEvent } from './miaosApi';
import { buildMiaosNodeIdMap } from './miaosExport';
import { applyRunEvent, delay, resetRunVisuals } from './runHighlight';

export type ReplayProgress = {
  index: number;
  event: MiaosGraphEvent;
  activeNodeId: string | null;
};

export function applyEventsUpTo(
  graph: Graph,
  events: MiaosGraphEvent[],
  upToIndex: number,
): string | null {
  const idMap = buildMiaosNodeIdMap(graph);
  resetRunVisuals(idMap);

  const lastIndex = Math.min(upToIndex, events.length - 1);
  if (lastIndex < 0) {
    return null;
  }

  let activeNodeId: string | null = null;
  for (let index = 0; index <= lastIndex; index += 1) {
    activeNodeId = applyRunEvent(idMap, events[index]) ?? activeNodeId;
  }
  return activeNodeId;
}

export async function replayGraphEvents(
  graph: Graph,
  events: MiaosGraphEvent[],
  options: {
    stepMs?: number;
    startIndex?: number;
    endIndex?: number;
    onProgress?: (progress: ReplayProgress) => void;
    signal?: AbortSignal;
  } = {},
): Promise<void> {
  const { stepMs = 400, startIndex = 0, endIndex = events.length, onProgress, signal } = options;
  const idMap = buildMiaosNodeIdMap(graph);
  resetRunVisuals(idMap);

  const safeEnd = Math.min(endIndex, events.length);
  for (let index = startIndex; index < safeEnd; index += 1) {
    if (signal?.aborted) {
      resetRunVisuals(idMap);
      throw new DOMException('Replay aborted', 'AbortError');
    }

    const event = events[index];
    const activeNodeId = applyRunEvent(idMap, event);
    onProgress?.({ index, event, activeNodeId });

    if (index < safeEnd - 1) {
      await delay(stepMs);
    }
  }
}
