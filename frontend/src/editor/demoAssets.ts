import type { MiaosModelRegisterPayload, MiaosPersonaProfile } from './miaosApi';
import { DEFAULT_MIAOS_PROVIDER } from './miaosApi';

export const DEMO_MODELS: MiaosModelRegisterPayload[] = [
  {
    repo: 'qwen3.5-8b',
    family: 'qwen3.5',
    params_billion: 8,
    quant: '4bit',
    size_bytes: 5_000_000_000,
    context_len: 32768,
    path: '/models/qwen3.5-8b',
    pool_role: 'worker',
  },
  {
    repo: 'qwen3.5-14b-pro-65k',
    family: 'qwen3.5',
    params_billion: 14,
    quant: '4bit',
    size_bytes: 11_000_000_000,
    context_len: 65536,
    path: '/models/qwen3.5-14b-pro-65k',
    pool_role: 'worker',
  },
  {
    repo: 'qwen3.5-coder-7b',
    family: 'qwen3.5-coder',
    params_billion: 7,
    quant: '4bit',
    size_bytes: 4_500_000_000,
    context_len: 32768,
    path: '/models/qwen3.5-coder-7b',
    pool_role: 'worker',
  },
  {
    repo: 'qwen3.5-4b',
    family: 'qwen3.5',
    params_billion: 4,
    quant: '4bit',
    size_bytes: 2_800_000_000,
    context_len: 32768,
    path: '/models/qwen3.5-4b',
    pool_role: 'router',
  },
];

export const MIA_GRAPH_FILENAME = 'mia-minimal.json';

export function buildMiaProfile(provider = DEFAULT_MIAOS_PROVIDER): MiaosPersonaProfile {
  return {
    identity: {
      role: 'Когнитивный исполнитель',
      default_locale: 'ru-RU',
      biography_seed: 'Mia — виртуальная личность для локального MAS на Apple Silicon.',
    },
    values: {
      ranked: ['honesty', 'care', 'curiosity'],
    },
    model_binding: {
      provider,
      model_id: 'qwen3.5-8b',
      runtime_profile: 'macbook_air_m4_32gb',
    },
    autonomy_contract: {
      contract_id: 'supervised-default',
      path: 'autonomy/contract_ref.json',
      autonomy_ceiling: 'L3',
    },
  };
}
