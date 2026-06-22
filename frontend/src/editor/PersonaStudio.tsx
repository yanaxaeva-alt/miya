import { useCallback, useEffect, useRef, useState } from 'react';
import {
  createPersona,
  downloadPersonaExport,
  fetchPersonas,
  fetchProviders,
  importPersonaPackage,
  type MiaosPersonaManifest,
} from './miaosApi';
import { buildMiaProfile } from './demoAssets';
import { DEFAULT_PROVIDER, pickDefaultProvider } from './providerPrefs';

function formatTs(ts: string) {
  try {
    return new Date(ts).toLocaleString();
  } catch {
    return ts;
  }
}

function packageKey(persona: MiaosPersonaManifest) {
  return persona.package_id || persona.persona_id;
}

export function PersonaStudio() {
  const [personas, setPersonas] = useState<MiaosPersonaManifest[]>([]);
  const [loading, setLoading] = useState(false);
  const [creating, setCreating] = useState(false);
  const [exportingId, setExportingId] = useState<string | null>(null);
  const [importing, setImporting] = useState(false);
  const [importPackageId, setImportPackageId] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const list = await fetchPersonas();
      setPersonas(list);
    } catch (err) {
      setPersonas([]);
      setError(err instanceof Error ? err.message : 'Не удалось загрузить persona packages');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  useEffect(() => {
    const onRefresh = () => void refresh();
    window.addEventListener('miya:studio-refresh', onRefresh);
    return () => window.removeEventListener('miya:studio-refresh', onRefresh);
  }, [refresh]);

  const createDemoMia = useCallback(async () => {
    setCreating(true);
    setError(null);
    setMessage(null);
    try {
      let provider = DEFAULT_PROVIDER;
      try {
        const providers = await fetchProviders();
        provider = pickDefaultProvider(providers);
      } catch {
        // keep DEFAULT_PROVIDER
      }
      const manifest = await createPersona('Mia', buildMiaProfile(provider), 'mia');
      setMessage(`Создан пакет «${manifest.name}» (${manifest.persona_id})`);
      await refresh();
      window.dispatchEvent(new CustomEvent('miya:studio-refresh'));
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Не удалось создать persona package');
    } finally {
      setCreating(false);
    }
  }, [refresh]);

  const exportPackage = useCallback(async (packageId: string) => {
    setExportingId(packageId);
    setError(null);
    setMessage(null);
    try {
      await downloadPersonaExport(packageId);
      setMessage(`Экспортирован ${packageId}.mia.zip`);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Не удалось экспортировать пакет');
    } finally {
      setExportingId(null);
    }
  }, []);

  const importPackage = useCallback(
    async (file: File) => {
      setImporting(true);
      setError(null);
      setMessage(null);
      try {
        const manifest = await importPersonaPackage(file, {
          packageId: importPackageId.trim() || undefined,
          overwrite: false,
        });
        setMessage(`Импортирован пакет «${manifest.name}» (${manifest.persona_id})`);
        setImportPackageId('');
        if (fileInputRef.current) fileInputRef.current.value = '';
        await refresh();
        window.dispatchEvent(new CustomEvent('miya:studio-refresh'));
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Не удалось импортировать пакет');
      } finally {
        setImporting(false);
      }
    },
    [importPackageId, refresh],
  );

  return (
    <section id="miya-persona-studio" className="miya-persona-studio">
      <div className="miya-run-header">
        <h2 className="miya-run-title">Persona Studio</h2>
        <span className="miya-run-badge">{personas.length} packages</span>
        <button
          type="button"
          className="miya-btn miya-btn-secondary"
          onClick={() => void refresh()}
          disabled={loading || creating || importing}
        >
          {loading ? 'Загрузка…' : 'Обновить'}
        </button>
        <button
          type="button"
          className="miya-btn"
          onClick={() => void createDemoMia()}
          disabled={loading || creating || importing}
        >
          {creating ? 'Создание…' : 'Создать Mia'}
        </button>
      </div>

      <p className="miya-run-hint">
        Каталог <code>.mia</code> persona packages из <code>GET /personas</code>. Экспорт —
        zip-архив для переноса; импорт — <code>POST /personas/import</code>.
      </p>

      <div className="miya-persona-import-row">
        <label className="miya-field miya-persona-import-field">
          <span>package_id при импорте (опционально)</span>
          <input
            type="text"
            value={importPackageId}
            onChange={(event) => setImportPackageId(event.target.value)}
            placeholder="mia-copy"
            disabled={importing}
          />
        </label>
        <input
          ref={fileInputRef}
          type="file"
          accept=".zip,application/zip"
          hidden
          onChange={(event) => {
            const file = event.target.files?.[0];
            if (file) void importPackage(file);
          }}
        />
        <button
          type="button"
          className="miya-btn miya-btn-secondary"
          onClick={() => fileInputRef.current?.click()}
          disabled={importing || loading}
        >
          {importing ? 'Импорт…' : 'Импорт .mia.zip'}
        </button>
      </div>

      {message && <p className="miya-persona-message">{message}</p>}
      {error && <pre className="miya-run-error">{error}</pre>}

      {!loading && !error && personas.length === 0 && (
        <p className="miya-run-hint">
          Пакетов пока нет. Нажмите <strong>Создать Mia</strong> или импортируйте{' '}
          <code>.mia.zip</code>.
        </p>
      )}

      {personas.length > 0 && (
        <div className="miya-model-table-wrap">
          <table className="miya-model-table">
            <thead>
              <tr>
                <th>Имя</th>
                <th>persona_id</th>
                <th>package_id</th>
                <th>Версия</th>
                <th>Создан</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {personas.map((persona) => {
                const id = packageKey(persona);
                return (
                  <tr key={persona.persona_id}>
                    <td>
                      <strong>{persona.name}</strong>
                      <div className="miya-model-id">
                        <code>{persona.model_binding_path}</code> ·{' '}
                        <code>{persona.autonomy_contract_ref_path}</code>
                      </div>
                    </td>
                    <td>
                      <code>{persona.persona_id}</code>
                    </td>
                    <td>
                      <code>{id}</code>
                    </td>
                    <td>{persona.version}</td>
                    <td>{formatTs(persona.created_at)}</td>
                    <td>
                      <button
                        type="button"
                        className="miya-btn miya-btn-secondary"
                        onClick={() => void exportPackage(id)}
                        disabled={exportingId === id}
                      >
                        {exportingId === id ? '…' : 'Экспорт'}
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
