import type { MiaosProviderInfo } from './miaosApi';
import { DEFAULT_MIAOS_PROVIDER } from './miaosApi';

export { DEFAULT_MIAOS_PROVIDER as DEFAULT_PROVIDER } from './miaosApi';

export function pickDefaultProvider(providers: MiaosProviderInfo[]): string {
  const configured = providers.find((item) => item.default && item.available);
  if (configured) return configured.name;
  const omlx = providers.find((item) => item.name === 'omlx' && item.available);
  if (omlx) return 'omlx';
  const mlx = providers.find((item) => item.name === 'mlx' && item.available);
  if (mlx) return 'mlx';
  const mock = providers.find((item) => item.name === 'mock' && item.available);
  if (mock) return 'mock';
  return providers.find((item) => item.available)?.name ?? DEFAULT_MIAOS_PROVIDER;
}

export function isMlxAvailable(providers: MiaosProviderInfo[]): boolean {
  return providers.some((item) => item.name === 'mlx' && item.available);
}
