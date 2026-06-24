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

export function providerDisplayName(providerName: string): string {
  if (providerName === 'omlx') return 'oMLX локально';
  if (providerName === 'mlx') return 'MLX напрямую';
  if (providerName === 'mock') return 'Тестовый режим';
  return providerName;
}

export function providerDescription(provider: MiaosProviderInfo | undefined): string {
  if (!provider) return '';
  if (provider.name === 'omlx') {
    return 'Основной локальный сервер oMLX. Подходит для обычной работы Mia и AEON.';
  }
  if (provider.name === 'mlx') {
    return 'Запасной прямой запуск через mlx-lm. Первый запуск может скачать веса модели.';
  }
  if (provider.name === 'mock') {
    return 'Тестовый режим без реальной модели. Нужен для проверки интерфейса и сценариев.';
  }
  return provider.description;
}
