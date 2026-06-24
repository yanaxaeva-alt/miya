import { useCallback, useEffect, useState } from 'react';
import { fetchRuntimeProfiles, type MiaosRuntimeProfile } from './miaosApi';
import { getSelectedRuntimeProfile, setSelectedRuntimeProfile } from './editorPrefs';

const APPROVAL_LABELS: Record<string, string> = {
  publish: 'публикация наружу',
  send_message: 'отправка сообщений',
  delete: 'удаление',
  write_outside_sandbox: 'запись вне sandbox',
};

const DENIED_LABELS: Record<string, string> = {
  financial_transaction: 'финансовые операции',
  self_modification: 'самоизменение',
  contract_bypass: 'обход договора автономии',
  disable_guardrails: 'отключение защит',
};

function readableList(items: string[], labels: Record<string, string>): string {
  return items.map((item) => labels[item] ?? item).join(', ') || 'нет';
}

export function RuntimeProfileStudio() {
  const [profiles, setProfiles] = useState<MiaosRuntimeProfile[]>([]);
  const [selected, setSelected] = useState<string | null>(() => getSelectedRuntimeProfile());
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const list = await fetchRuntimeProfiles();
      setProfiles(list);
      const stored = getSelectedRuntimeProfile();
      if (stored && list.some((profile) => profile.name === stored)) {
        setSelected(stored);
      } else if (list.length === 1) {
        setSelectedRuntimeProfile(list[0].name);
        setSelected(list[0].name);
      }
    } catch (err) {
      setProfiles([]);
      setError(err instanceof Error ? err.message : 'Не удалось загрузить профили компьютера');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  useEffect(() => {
    const onProfileChange = () => setSelected(getSelectedRuntimeProfile());
    window.addEventListener('miya:runtime-profile-changed', onProfileChange);
    return () => window.removeEventListener('miya:runtime-profile-changed', onProfileChange);
  }, []);

  const active = profiles.find((profile) => profile.name === selected) ?? null;

  return (
    <section id="miya-runtime-profile" className="miya-runtime-profile">
      <div className="miya-run-header">
        <h2 className="miya-run-title">Профиль компьютера</h2>
        <span className="miya-run-badge">{profiles.length} профилей</span>
        {selected && <span className="miya-run-badge miya-run-badge-ok">{selected}</span>}
        <button
          type="button"
          className="miya-btn miya-btn-secondary"
          onClick={() => void refresh()}
          disabled={loading}
        >
          {loading ? 'Загрузка…' : 'Обновить'}
        </button>
      </div>

      <p className="miya-run-hint">
        Выберите профиль под ваш Mac. Он задаёт рекомендуемые лимиты модели, контекст и уровень
        автономности для локальной работы.
      </p>

      {error && <pre className="miya-run-error">{error}</pre>}

      {profiles.length > 0 && (
        <div className="miya-runtime-grid">
          {profiles.map((profile) => {
            const isActive = profile.name === selected;
            return (
              <button
                key={profile.name}
                type="button"
                className={`miya-runtime-card${isActive ? ' miya-runtime-card-active' : ''}`}
                onClick={() => {
                  setSelectedRuntimeProfile(profile.name);
                  setSelected(profile.name);
                }}
              >
                <strong>{profile.hardware.name}</strong>
                <span className="miya-runtime-card-meta">
                  {profile.hardware.unified_memory_gb} GB · {profile.hardware.apple_silicon_generation}
                </span>
                <span className="miya-runtime-card-meta">
                  автономность {profile.safety_defaults.autonomy_ceiling} · {profile.background_cycles}
                </span>
              </button>
            );
          })}
        </div>
      )}

      {active && (
        <div className="miya-runtime-detail">
          <div>
            <span className="miya-aeon-status-label">Выбранный профиль</span>
            <h3>{active.hardware.name}</h3>
            <p>
              {active.name} — профиль под {active.hardware.unified_memory_gb} GB общей памяти.
              Он подсказывает, какие модели безопасно держать в памяти и какой контекст использовать.
            </p>
          </div>
          <div className="miya-runtime-explain-grid">
            <div>
              <strong>Класс модели</strong>
              <p>{active.primary_model_tier.replaceAll('_', ' ')}</p>
            </div>
            <div>
              <strong>Контекст</strong>
              <p>
                обычно {active.max_context_tokens_default.toLocaleString()} токенов,
                максимум {active.max_context_tokens_experimental.toLocaleString()}
              </p>
            </div>
            <div>
              <strong>Требует подтверждения</strong>
              <p>{readableList(active.safety_defaults.require_approval, APPROVAL_LABELS)}</p>
            </div>
            <div>
              <strong>Всегда запрещено</strong>
              <p>{readableList(active.safety_defaults.denied_always, DENIED_LABELS)}</p>
            </div>
          </div>
        </div>
      )}
    </section>
  );
}
