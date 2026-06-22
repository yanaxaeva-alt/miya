import type { MiaosGraphEvent, MiaosTraceEvent } from './miaosApi';

export interface TraceTimelineItem {
  id: string;
  source: 'run' | 'audit';
  ts: string;
  kind: string;
  actor: string;
  summary: string;
  nodeId?: string | null;
}

export interface PolicyDecisionRow {
  id: string;
  ts: string;
  eventType: string;
  actionClass: string;
  outcome: string;
  actor: string;
  summary: string;
}

const POLICY_EVENT_TYPES = new Set(['policy_decision', 'human_approval']);

function parsePolicySummary(summary: string): { actionClass: string; outcome: string } | null {
  const match = summary.match(/^(\S+)\s*->\s*(.+)$/);
  if (!match) return null;
  const actionClass = match[1];
  let outcome = match[2].trim();
  if (outcome.endsWith(' by human')) {
    outcome = outcome.replace(/ by human$/, '');
  }
  return { actionClass, outcome };
}

export function isPolicyEvent(event: MiaosTraceEvent): boolean {
  return POLICY_EVENT_TYPES.has(event.event_type);
}

export function buildPolicyRows(events: MiaosTraceEvent[]): PolicyDecisionRow[] {
  return events
    .filter(isPolicyEvent)
    .map((event, index) => {
      const parsed = parsePolicySummary(event.summary);
      return {
        id: event.event_hash ?? `${event.ts}-${index}`,
        ts: event.ts,
        eventType: event.event_type,
        actionClass: parsed?.actionClass ?? '—',
        outcome: parsed?.outcome ?? event.summary,
        actor: event.actor,
        summary: event.summary,
      };
    });
}

export function buildTraceTimeline(
  auditEvents: MiaosTraceEvent[],
  runEvents: MiaosGraphEvent[] = [],
): TraceTimelineItem[] {
  const auditItems: TraceTimelineItem[] = auditEvents.map((event, index) => ({
    id: `audit-${event.event_hash ?? index}`,
    source: 'audit',
    ts: event.ts,
    kind: event.event_type,
    actor: event.actor,
    summary: event.summary,
  }));

  const runItems: TraceTimelineItem[] = runEvents.map((event, index) => ({
    id: `run-${event.run_id}-${event.event_type}-${index}`,
    source: 'run',
    ts: event.ts ?? new Date(0).toISOString(),
    kind: event.event_type,
    actor: 'graph_runner',
    summary: event.message,
    nodeId: event.node_id,
  }));

  return [...auditItems, ...runItems].sort(
    (a, b) => new Date(a.ts).getTime() - new Date(b.ts).getTime(),
  );
}

export function formatTraceTime(ts: string): string {
  try {
    return new Date(ts).toLocaleTimeString();
  } catch {
    return ts;
  }
}

export function policyOutcomeClass(outcome: string): string {
  const value = outcome.toLowerCase();
  if (value.includes('allow') || value.includes('approved')) return 'miya-policy-allow';
  if (value.includes('deny') || value.includes('rejected')) return 'miya-policy-deny';
  if (value.includes('require_approval') || value.includes('approval')) {
    return 'miya-policy-approval';
  }
  return 'miya-policy-neutral';
}
