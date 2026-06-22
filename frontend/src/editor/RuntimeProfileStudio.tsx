import { useCallback, useEffect, useState } from 'react';
import { fetchRuntimeProfiles, type MiaosRuntimeProfile } from './miaosApi';
import { getSelectedRuntimeProfile, setSelectedRuntimeProfile } from './editorPrefs';

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
      setError(err instanceof Error ? err.message : 'Не удалось загрузить runtime profiles');
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
        <h2 className="miya-run-title">Runtime Profile</h2>
        <span className="miya-run-badge">{profiles.length} profiles</span>
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
        Профиль железа из <code>GET /runtime/profiles</code>. Выбор сохраняется в браузере и задаёт
        рекомендуемые лимиты моделей и safety defaults для сценариев v1.0.
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
                  ceiling {profile.safety_defaults.autonomy_ceiling} · {profile.background_cycles}
                </span>
              </button>
            );
          })}
        </div>
      )}

      {active && (
        <div className="miya-runtime-detail">
          <p>
            <strong>{active.name}</strong> · tier {active.primary_model_tier} · context{' '}
            {active.max_context_tokens_default.toLocaleString()} /{' '}
            {active.max_context_tokens_experimental.toLocaleString()}
          </p>
          <p className="miya-run-hint">
            require_approval: {active.safety_defaults.require_approval.join(', ') || '—'} · denied:{' '}
            {active.safety_defaults.denied_always.join(', ')}
          </p>
        </div>
      )}
    </section>
  );
}
