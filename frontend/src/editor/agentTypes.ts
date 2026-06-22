export type AgentStatus = 'idle' | 'running' | 'error';

export type AgentRole = 'planner' | 'executor' | 'memory' | 'perception' | 'critic';

export interface AgentNodeData {
  name?: string;
  model?: string;
  status?: AgentStatus;
  role?: AgentRole | string;
  active?: boolean;
}

export const AGENT_MODELS = [
  'qwen3.5-8b',
  'qwen3.5-coder-7b',
  'qwen3.5-4b',
] as const;

export const AGENT_ROLES: { value: AgentRole; label: string }[] = [
  { value: 'planner', label: 'Планировщик' },
  { value: 'executor', label: 'Исполнитель' },
  { value: 'critic', label: 'Критик' },
  { value: 'memory', label: 'Память' },
  { value: 'perception', label: 'Восприятие' },
];

export const SANDBOX_TOOL_NAMES = [
  'read_file_sandbox',
  'write_file_sandbox',
  'web_search_mock',
  'create_draft',
] as const;

export type ToolNodeData = {
  name?: string;
  tool_name?: string;
  status?: AgentStatus;
  active?: boolean;
};

export const AGENT_STATUSES: { value: AgentStatus; label: string }[] = [
  { value: 'idle', label: 'idle — простой' },
  { value: 'running', label: 'running — работает' },
  { value: 'error', label: 'error — ошибка' },
];
