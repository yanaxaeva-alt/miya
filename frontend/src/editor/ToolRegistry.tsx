import { useCallback, useEffect, useState } from 'react';
import { fetchTools, type MiaosToolSpec } from './miaosApi';

function toolNameLabel(name: string): string {
  if (name === 'web_search_mock') return 'Поиск в интернете';
  if (name === 'create_draft') return 'Черновик ответа';
  if (name === 'read_file_sandbox') return 'Чтение файла';
  if (name === 'write_file_sandbox') return 'Запись файла';
  return name;
}

function toolDescription(tool: MiaosToolSpec): string {
  if (tool.name === 'web_search_mock') return 'Тестовый поиск для сценариев без доступа к внешним сервисам.';
  if (tool.name === 'create_draft') return 'Создаёт черновик текста внутри графа.';
  if (tool.name === 'read_file_sandbox') return 'Читает файл только в разрешённой области.';
  if (tool.name === 'write_file_sandbox') return 'Записывает файл только в разрешённой области.';
  return tool.description;
}

function actionClassLabel(actionClass: string): string {
  if (actionClass === 'read') return 'чтение';
  if (actionClass === 'write') return 'запись';
  if (actionClass === 'publish') return 'публикация';
  if (actionClass === 'send_message') return 'сообщение';
  return actionClass;
}

export function ToolRegistry() {
  const [tools, setTools] = useState<MiaosToolSpec[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const list = await fetchTools();
      setTools(list);
    } catch (err) {
      setTools([]);
      setError(err instanceof Error ? err.message : 'Не удалось загрузить инструменты');
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

  return (
    <section id="miya-tool-registry" className="miya-tool-registry">
      <div className="miya-run-header">
        <h2 className="miya-run-title">Инструменты</h2>
        <span className="miya-run-badge">{tools.length} инструментов</span>
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
        Каталог инструментов, которые можно вызывать из графа. Они проходят проверку безопасности
        и выполняются только в изолированном режиме.
      </p>

      {error && <pre className="miya-run-error">{error}</pre>}

      {!loading && !error && tools.length === 0 && (
        <p className="miya-run-hint">
          Реестр пуст. Перезапустите backend с новым кодом MiaOS.
        </p>
      )}

      {tools.length > 0 && (
        <div className="miya-model-table-wrap">
          <table className="miya-model-table">
            <thead>
              <tr>
                <th>Инструмент</th>
                <th>Класс действия</th>
                <th>Песочница</th>
                <th>Статус</th>
              </tr>
            </thead>
            <tbody>
              {tools.map((tool) => (
                <tr key={tool.name}>
                  <td>
                    <strong>{toolNameLabel(tool.name)}</strong>
                    <div className="miya-model-id">{toolDescription(tool)}</div>
                  </td>
                  <td>{actionClassLabel(tool.action_class)}</td>
                  <td>{tool.sandbox_only ? 'да' : 'нет'}</td>
                  <td>
                    <span
                      className={`miya-model-status ${
                        tool.enabled ? 'miya-model-status-active' : 'miya-model-status-archived'
                      }`}
                    >
                      {tool.enabled ? 'включён' : 'выключен'}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
