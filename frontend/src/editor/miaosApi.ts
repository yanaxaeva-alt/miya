import type { MiaosGraphSpec } from './miaosExport';

const API_BASE = import.meta.env.VITE_MIAOS_API_URL || '/api/miaos';

export const DEFAULT_MIAOS_PROVIDER = 'mlx';

export interface MiaosGraphEvent {
  run_id: string;
  trace_id: string;
  event_type: string;
  node_id?: string | null;
  message: string;
  payload?: Record<string, string | number | boolean>;
  ts?: string;
}

export interface MiaosGraphRun {
  run_id: string;
  trace_id: string;
  graph_id: string;
  status: string;
  provider?: string;
  approval_request_id?: string;
  events: MiaosGraphEvent[];
  outputs: Record<string, string>;
}

export interface MiaosApprovalResolveResponse {
  request: MiaosApprovalRequest;
  resumed_run?: MiaosGraphRun;
}

export interface MiaosApprovalRequest {
  request_id: string;
  run_id: string;
  trace_id: string;
  graph_id: string;
  node_id: string;
  action_class: string;
  summary: string;
  status: 'pending' | 'approved' | 'rejected';
  created_at: string;
  resolved_at?: string | null;
  resolved_by?: string | null;
}

export interface MiaosProviderInfo {
  name: string;
  available: boolean;
  description: string;
}

export interface MiaosToolSpec {
  name: string;
  description: string;
  action_class: string;
  sandbox_only: boolean;
  enabled: boolean;
  requires_approval: boolean;
}

export interface MiaosModelRecord {
  id: string;
  repo: string;
  family: string;
  params_billion: number;
  active_params_billion?: number | null;
  is_moe: boolean;
  quant: string;
  size_bytes: number;
  context_len: number;
  path: string;
  pool_role?: string | null;
  status: string;
  tok_per_sec?: number | null;
  checksum_sha256?: string | null;
  added_at?: string;
  last_used?: string | null;
  lab_cert?: string | null;
  notes?: string | null;
}

export interface MiaosModelRegisterPayload {
  repo: string;
  family: string;
  params_billion: number;
  quant: string;
  size_bytes: number;
  context_len: number;
  path: string;
  pool_role?: string | null;
}

export type MiaosLabCertStatus =
  | 'pending'
  | 'passed'
  | 'failed'
  | 'certified'
  | 'conditional'
  | 'rejected';

export interface MiaosCompatibilityWarning {
  code: string;
  severity: 'info' | 'warning' | 'error';
  message: string;
}

export interface MiaosModelCompatibilityReport {
  model_id: string;
  profile_name: string;
  pool_role: string;
  selectable: boolean;
  compatible: boolean;
  recommended: boolean;
  warnings: MiaosCompatibilityWarning[];
}

export interface MiaosPersonaManifest {
  mia_format_version: string;
  persona_id: string;
  name: string;
  version: string;
  created_at: string;
  updated_at: string;
  identity_path: string;
  values_path: string;
  model_binding_path: string;
  autonomy_contract_ref_path: string;
  package_id?: string;
}

export interface MiaosChatTurn {
  trace_id: string;
  user_message: string;
  response_text: string;
  blocked: boolean;
  policy_decision: {
    decision: string;
    reason: string;
    trace_id: string;
  };
}

export interface MiaosAeonGoal {
  id: string;
  title: string;
  description: string;
  priority: number;
  progress: number;
  source: string;
  active: boolean;
}

export interface MiaosAeonStatus {
  available?: boolean;
  version?: string;
  identity: string;
  values: string[];
  provider: string;
  heartbeat_interval_seconds?: number;
  consolidation_interval_hours?: number;
  active_goals: MiaosAeonGoal[];
  recent_episodes: string[];
  skill_hints: string[];
  recent_ticks?: MiaosAeonTickResult[];
  watch_dirs?: string[];
}

export interface MiaosAeonConsolidationResult {
  retired_goal_ids: string[];
  active_goal_count: number;
  episodes_seen: number;
  skill_recorded: boolean;
  summary?: string;
}

export interface MiaosAeonResponse {
  trace_id: string;
  text: string;
  execution_mode: 'chat' | 'graph';
  graph_id?: string | null;
  blocked: boolean;
  constitutional: {
    allowed: boolean;
    tier: string;
    reason: string;
    requires_human?: boolean;
  };
  governance: {
    safety_ok: boolean;
    drift_ok: boolean;
    anomaly_ok: boolean;
    notes: string[];
  };
  goal_id?: string | null;
  metadata?: Record<string, string | boolean | number>;
}

export interface MiaosAeonTickResult {
  tick_id: string;
  surprise: string;
  surprise_score: number;
  action: string;
  governance_ok: boolean;
  curiosity_goal_id?: string;
  plan_recorded?: boolean;
  monitor_recorded?: boolean;
}

export type MiaosPersonaProfile = Record<string, unknown>;

export interface MiaosRuntimeProfile {
  name: string;
  role: string;
  hardware: {
    name: string;
    unified_memory_gb: number;
    apple_silicon_generation: string;
  };
  primary_model_tier: string;
  large_model_mode: string;
  max_context_tokens_default: number;
  max_context_tokens_experimental: number;
  background_cycles: string;
  always_busy: boolean | string;
  thermal_policy: string;
  vector_db: string;
  observability: string;
  safety_defaults: {
    autonomy_ceiling: string;
    require_approval: string[];
    denied_always: string[];
  };
}

export interface MiaosGraphLibraryItem {
  filename: string;
  graph_id: string;
  name: string;
  node_count: number;
}

export interface MiaosTemplateItem {
  template_id: string;
  name: string;
  description: string;
  category: string;
  tags: string[];
  graph_id: string;
  node_count: number;
}

export interface MiaosTemplateDetail extends MiaosTemplateItem {
  graph: MiaosGraphSpec;
}

export interface MiaosTraceEvent {
  ts: string;
  event_type: string;
  trace_id: string;
  summary: string;
  actor: string;
  refs?: Record<string, string>;
  previous_hash?: string;
  event_hash?: string;
}

export interface MiaosTraceResponse {
  trace_id: string;
  events: MiaosTraceEvent[];
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      'Content-Type': 'application/json',
      ...(init?.headers || {}),
    },
  });

  if (!response.ok) {
    let detail = response.statusText;
    try {
      const body = (await response.json()) as { detail?: string | Array<{ msg: string }> };
      if (typeof body.detail === 'string') detail = body.detail;
      else if (Array.isArray(body.detail)) detail = body.detail.map((item) => item.msg).join('; ');
    } catch {
      // keep statusText
    }
    throw new Error(detail || `HTTP ${response.status}`);
  }

  return response.json() as Promise<T>;
}

export async function checkMiaosHealth(): Promise<boolean> {
  try {
    const body = await request<{ status: string }>('/health');
    return body.status === 'ok';
  } catch {
    return false;
  }
}

export async function validateMiaosGraphRemote(graph: MiaosGraphSpec) {
  return request<{ valid: boolean; graph_id: string; name: string }>('/graphs/validate', {
    method: 'POST',
    body: JSON.stringify({ graph }),
  });
}

export async function fetchProviders() {
  return request<MiaosProviderInfo[]>('/providers');
}

export async function fetchTools() {
  return request<MiaosToolSpec[]>('/tools');
}

export interface MiaosQualityDataset {
  name: string;
  description: string;
  case_count: number;
  min_pass_rate: number;
  suites: string[];
}

export interface MiaosEvalResult {
  case_id: string;
  suite: string;
  passed: boolean;
  detail: string;
}

export interface MiaosEvalReport {
  dataset: string;
  provider: string;
  passed: number;
  failed: number;
  pass_rate: number;
  min_pass_rate: number;
  gate_passed: boolean;
  results: MiaosEvalResult[];
}

export async function fetchQualityDatasets() {
  return request<MiaosQualityDataset[]>('/quality/datasets');
}

export async function runQualityEval(
  dataset = 'golden_mvp',
  provider = DEFAULT_MIAOS_PROVIDER,
  packageId = 'mia',
) {
  return request<MiaosEvalReport>('/quality/eval', {
    method: 'POST',
    body: JSON.stringify({ dataset, provider, package_id: packageId }),
  });
}

export interface MiaosMemorySummary {
  package_id: string;
  episodes: number;
  profile_facts: number;
  domain_notes: number;
  deletions_logged: number;
}

export interface MiaosMemoryEpisode {
  id: string;
  package_id: string;
  trace_id?: string | null;
  role: string;
  content: string;
  tags: string[];
  created_at: string;
}

export interface MiaosProfileFact {
  id: string;
  package_id: string;
  key: string;
  value: string;
  created_at: string;
  updated_at: string;
}

export interface MiaosDomainNote {
  id: string;
  package_id: string;
  domain: string;
  content: string;
  tags: string[];
  created_at: string;
}

export async function fetchMemorySummary(packageId = 'mia') {
  return request<MiaosMemorySummary>(`/memory/summary?package_id=${encodeURIComponent(packageId)}`);
}

export async function fetchMemoryEpisodes(packageId = 'mia') {
  return request<MiaosMemoryEpisode[]>(
    `/memory/episodes?package_id=${encodeURIComponent(packageId)}`,
  );
}

export async function deleteMemoryEpisode(episodeId: string, packageId = 'mia') {
  return request<{ status: string; episode_id: string }>(
    `/memory/episodes/${encodeURIComponent(episodeId)}?package_id=${encodeURIComponent(packageId)}`,
    { method: 'DELETE' },
  );
}

export async function fetchProfileFacts(packageId = 'mia') {
  return request<MiaosProfileFact[]>(`/memory/profile?package_id=${encodeURIComponent(packageId)}`);
}

export async function upsertProfileFact(key: string, value: string, packageId = 'mia') {
  return request<MiaosProfileFact>('/memory/profile', {
    method: 'POST',
    body: JSON.stringify({ package_id: packageId, key, value }),
  });
}

export async function fetchDomainNotes(packageId = 'mia') {
  return request<MiaosDomainNote[]>(`/memory/notes?package_id=${encodeURIComponent(packageId)}`);
}

export async function addDomainNote(
  domain: string,
  content: string,
  packageId = 'mia',
  tags: string[] = [],
) {
  return request<MiaosDomainNote>('/memory/notes', {
    method: 'POST',
    body: JSON.stringify({ package_id: packageId, domain, content, tags }),
  });
}

export async function deleteDomainNote(noteId: string, packageId = 'mia') {
  return request<{ status: string; note_id: string }>(
    `/memory/notes/${encodeURIComponent(noteId)}?package_id=${encodeURIComponent(packageId)}`,
    { method: 'DELETE' },
  );
}

export async function fetchModels() {
  return request<MiaosModelRecord[]>('/models');
}

export async function deleteDemoModels() {
  return request<{ status: string; deleted: number; repos: string[] }>('/models/demo', {
    method: 'DELETE',
  });
}

export async function fetchModelCompatibility(
  profileName: string,
  role: 'router' | 'worker' | 'moe_expert' | 'deep' = 'worker',
) {
  const params = new URLSearchParams({ profile_name: profileName, role });
  return request<MiaosModelCompatibilityReport[]>(`/models/compatibility?${params.toString()}`);
}

export async function setModelLabCert(modelId: string, labCert: MiaosLabCertStatus | null) {
  return request<MiaosModelRecord>(`/models/${encodeURIComponent(modelId)}/lab-cert`, {
    method: 'PATCH',
    body: JSON.stringify({ lab_cert: labCert }),
  });
}

export async function registerMiaosModel(payload: MiaosModelRegisterPayload) {
  return request<MiaosModelRecord>('/models/register', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function fetchPersonas() {
  return request<MiaosPersonaManifest[]>('/personas');
}

export async function createPersona(
  name: string,
  profile: MiaosPersonaProfile,
  packageId = 'mia',
) {
  return request<MiaosPersonaManifest>('/personas', {
    method: 'POST',
    body: JSON.stringify({ name, profile, package_id: packageId }),
  });
}

export async function fetchRuntimeProfiles() {
  return request<MiaosRuntimeProfile[]>('/runtime/profiles');
}

export async function downloadPersonaExport(packageId: string) {
  const response = await fetch(`${API_BASE}/personas/${encodeURIComponent(packageId)}/export`);
  if (!response.ok) {
    let detail = response.statusText;
    try {
      const body = (await response.json()) as { detail?: string };
      if (typeof body.detail === 'string') detail = body.detail;
    } catch {
      // keep statusText
    }
    throw new Error(detail || `HTTP ${response.status}`);
  }

  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = `${packageId}.mia.zip`;
  anchor.click();
  URL.revokeObjectURL(url);
}

export async function importPersonaPackage(
  file: File,
  options?: { packageId?: string; overwrite?: boolean },
) {
  const form = new FormData();
  form.append('file', file);
  if (options?.packageId) form.append('package_id', options.packageId);
  form.append('overwrite', options?.overwrite ? 'true' : 'false');

  const response = await fetch(`${API_BASE}/personas/import`, {
    method: 'POST',
    body: form,
  });

  if (!response.ok) {
    let detail = response.statusText;
    try {
      const body = (await response.json()) as { detail?: string };
      if (typeof body.detail === 'string') detail = body.detail;
    } catch {
      // keep statusText
    }
    throw new Error(detail || `HTTP ${response.status}`);
  }

  return response.json() as Promise<MiaosPersonaManifest>;
}

export async function fetchTemplates() {
  return request<MiaosTemplateItem[]>('/templates');
}

export async function fetchTemplate(templateId: string) {
  return request<MiaosTemplateDetail>(`/templates/${encodeURIComponent(templateId)}`);
}

export async function instantiateTemplate(templateId: string, graphId?: string, name?: string) {
  return request<MiaosGraphSpec>(`/templates/${encodeURIComponent(templateId)}/instantiate`, {
    method: 'POST',
    body: JSON.stringify({ graph_id: graphId, name }),
  });
}

export async function fetchGraphLibrary() {
  return request<MiaosGraphLibraryItem[]>('/graphs');
}

export async function fetchSavedGraph(filename: string) {
  return request<MiaosGraphSpec>(`/graphs/${encodeURIComponent(filename)}`);
}

export async function saveGraphToLibrary(graph: MiaosGraphSpec, filename?: string) {
  return request<MiaosGraphLibraryItem>('/graphs', {
    method: 'POST',
    body: JSON.stringify({ graph, filename }),
  });
}

export async function sendChatMessage(
  message: string,
  packageId = 'mia',
  provider = DEFAULT_MIAOS_PROVIDER,
) {
  return request<MiaosChatTurn>('/chat', {
    method: 'POST',
    body: JSON.stringify({ message, package_id: packageId, provider }),
  });
}

export async function fetchAeonStatus(packageId = 'mia') {
  return request<MiaosAeonStatus>(`/aeon/status?package_id=${encodeURIComponent(packageId)}`);
}

export async function sendAeonMessage(
  message: string,
  options?: { provider?: string; forceGraph?: boolean; packageId?: string },
) {
  return request<MiaosAeonResponse>('/aeon/ask', {
    method: 'POST',
    body: JSON.stringify({
      message,
      provider: options?.provider ?? DEFAULT_MIAOS_PROVIDER,
      force_graph: options?.forceGraph ?? false,
      package_id: options?.packageId ?? 'mia',
    }),
  });
}

export async function runAeonTick(packageId = 'mia') {
  return request<MiaosAeonTickResult>(`/aeon/tick?package_id=${encodeURIComponent(packageId)}`, {
    method: 'POST',
  });
}

export async function addAeonGoal(
  title: string,
  description: string,
  options?: { priority?: number; provider?: string; packageId?: string },
) {
  return request<MiaosAeonGoal>('/aeon/goals', {
    method: 'POST',
    body: JSON.stringify({
      title,
      description,
      priority: options?.priority ?? 0.6,
      provider: options?.provider ?? DEFAULT_MIAOS_PROVIDER,
      package_id: options?.packageId ?? 'mia',
    }),
  });
}

export async function deactivateAeonGoal(goalId: string, packageId = 'mia') {
  return request<{ goal_id: string; active: boolean }>(
    `/aeon/goals/${encodeURIComponent(goalId)}/deactivate?package_id=${encodeURIComponent(packageId)}`,
    { method: 'POST' },
  );
}

export async function consolidateAeon(packageId = 'mia') {
  return request<MiaosAeonConsolidationResult>(
    `/aeon/consolidate?package_id=${encodeURIComponent(packageId)}`,
    { method: 'POST' },
  );
}

export async function checkAeonHealth(packageId = 'mia') {
  try {
    const status = await fetchAeonStatus(packageId);
    return Boolean(status.available);
  } catch {
    return false;
  }
}

export async function runMiaosGraph(
  graph: MiaosGraphSpec,
  inputText: string,
  provider = DEFAULT_MIAOS_PROVIDER,
) {
  return request<MiaosGraphRun>('/graphs/run', {
    method: 'POST',
    body: JSON.stringify({ graph, input_text: inputText, provider }),
  });
}

export async function fetchTrace(traceId: string) {
  return request<MiaosTraceResponse>(`/traces/${encodeURIComponent(traceId)}`);
}

export async function fetchRunEvents(runId: string) {
  return request<MiaosGraphEvent[]>(`/runs/${encodeURIComponent(runId)}/events`);
}

export async function fetchApprovals(status?: 'pending' | 'approved' | 'rejected') {
  const query = status ? `?status=${encodeURIComponent(status)}` : '';
  return request<MiaosApprovalRequest[]>(`/approvals${query}`);
}

export async function resolveApproval(
  requestId: string,
  decision: 'approved' | 'rejected',
  actor = 'human',
) {
  return request<MiaosApprovalResolveResponse>(`/approvals/${encodeURIComponent(requestId)}/resolve`, {
    method: 'POST',
    body: JSON.stringify({ decision, actor }),
  });
}

function getWsBase(): string {
  const api = import.meta.env.VITE_MIAOS_API_URL || '/api/miaos';
  if (api.startsWith('http://')) return api.replace(/^http/, 'ws');
  if (api.startsWith('https://')) return api.replace(/^https/, 'wss');
  const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  return `${proto}//${window.location.host}${api}`;
}

export function watchRunEvents(
  runId: string,
  onEvent: (event: MiaosGraphEvent) => void | Promise<void>,
  timeoutMs = 15000,
): Promise<void> {
  return new Promise((resolve, reject) => {
    const socket = new WebSocket(`${getWsBase()}/runs/${runId}/events`);
    let settled = false;

    const finish = (fn: () => void) => {
      if (settled) return;
      settled = true;
      window.clearTimeout(timer);
      fn();
    };

    const timer = window.setTimeout(() => {
      socket.close();
      finish(() => reject(new Error('WebSocket: таймаут ожидания событий')));
    }, timeoutMs);

    socket.onmessage = async (message) => {
      try {
        const event = JSON.parse(message.data as string) as MiaosGraphEvent;
        await onEvent(event);
      } catch (error) {
        finish(() => reject(error instanceof Error ? error : new Error('Bad WebSocket event')));
      }
    };

    socket.onerror = () => {
      finish(() => reject(new Error('WebSocket /runs/events недоступен')));
    };

    socket.onclose = () => {
      finish(resolve);
    };
  });
}
