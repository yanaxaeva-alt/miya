import { useCallback, useEffect, useState } from 'react';
import type { Graph } from '@antv/x6';
import {
  fetchTemplates,
  instantiateTemplate,
  saveGraphToLibrary,
  type MiaosTemplateItem,
} from './miaosApi';
import { importMiaosToCanvas } from './miaosImport';
import { setStatus } from '../miyaBridge';

interface TemplateRegistryProps {
  graph: Graph | null;
}

function filenameForTemplate(template: MiaosTemplateItem): string {
  return `${template.template_id}.json`;
}

export function TemplateRegistry({ graph }: TemplateRegistryProps) {
  const [templates, setTemplates] = useState<MiaosTemplateItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [workingId, setWorkingId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const list = await fetchTemplates();
      setTemplates(list);
    } catch (err) {
      setTemplates([]);
      setError(err instanceof Error ? err.message : 'Не удалось загрузить шаблоны');
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

  useEffect(() => {
    const onFocus = () =>
      document
        .getElementById('miya-template-registry')
        ?.scrollIntoView({ behavior: 'smooth', block: 'start' });
    window.addEventListener('miya:template-registry-focus', onFocus);
    return () => window.removeEventListener('miya:template-registry-focus', onFocus);
  }, []);

  const loadOntoCanvas = useCallback(
    async (template: MiaosTemplateItem) => {
      if (!graph) {
        window.alert('Подождите — холст ещё загружается.');
        return;
      }
      if (
        graph.getNodes().length > 0 &&
        !window.confirm(`Заменить текущий холст шаблоном «${template.name}»?`)
      ) {
        return;
      }

      setWorkingId(template.template_id);
      setError(null);
      setMessage(null);
      try {
        const spec = await instantiateTemplate(template.template_id);
        const count = importMiaosToCanvas(graph, spec);
        setMessage(`Шаблон «${template.name}» загружен на холст (${count} узлов)`);
        setStatus(`Template Registry → холст: ${template.template_id}`);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Не удалось создать граф из шаблона');
      } finally {
        setWorkingId(null);
      }
    },
    [graph],
  );

  const saveToLibrary = useCallback(async (template: MiaosTemplateItem) => {
    setWorkingId(template.template_id);
    setError(null);
    setMessage(null);
    try {
      const spec = await instantiateTemplate(template.template_id);
      const saved = await saveGraphToLibrary(spec, filenameForTemplate(template));
      setMessage(`Сохранено в Graph Library: ${saved.filename} (${saved.node_count} узлов)`);
      setStatus(`Template Registry → Library: ${saved.filename}`);
      window.dispatchEvent(new CustomEvent('miya:studio-refresh'));
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Не удалось сохранить шаблон');
    } finally {
      setWorkingId(null);
    }
  }, []);

  return (
    <section id="miya-template-registry" className="miya-template-registry">
      <div className="miya-run-header">
        <h2 className="miya-run-title">Template Registry</h2>
        <span className="miya-run-badge">{templates.length} templates</span>
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
        Каталог встроенных шаблонов из <code>GET /templates</code>. Factory endpoint{' '}
        <code>POST /templates/&#123;id&#125;/instantiate</code> создаёт MiaOS graph spec для холста
        или Graph Library.
      </p>

      {message && <p className="miya-persona-message">{message}</p>}
      {error && <pre className="miya-run-error">{error}</pre>}

      {!loading && !error && templates.length === 0 && (
        <p className="miya-run-hint">Шаблонов пока нет или backend нужно перезапустить.</p>
      )}

      {templates.length > 0 && (
        <div className="miya-template-grid">
          {templates.map((template) => (
            <article key={template.template_id} className="miya-template-card">
              <div className="miya-template-card-head">
                <strong>{template.name}</strong>
                <span className="miya-run-badge">{template.category}</span>
              </div>
              <p>{template.description}</p>
              <p className="miya-run-hint">
                <code>{template.template_id}</code> · {template.node_count} nodes
              </p>
              <div className="miya-template-tags">
                {template.tags.map((tag) => (
                  <span key={tag} className="miya-template-tag">
                    {tag}
                  </span>
                ))}
              </div>
              <div className="miya-template-actions">
                <button
                  type="button"
                  className="miya-btn miya-btn-secondary"
                  onClick={() => void loadOntoCanvas(template)}
                  disabled={!graph || workingId === template.template_id}
                >
                  На холст
                </button>
                <button
                  type="button"
                  className="miya-btn miya-btn-primary"
                  onClick={() => void saveToLibrary(template)}
                  disabled={workingId === template.template_id}
                >
                  В Library
                </button>
              </div>
            </article>
          ))}
        </div>
      )}
    </section>
  );
}
