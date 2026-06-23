import { useCallback, useEffect, useState } from 'react';
import {
  fetchPersonas,
  fetchProviders,
  sendChatMessage,
  type MiaosChatTurn,
  type MiaosPersonaManifest,
  type MiaosProviderInfo,
} from './miaosApi';
import { DEFAULT_PROVIDER, isMlxAvailable, pickDefaultProvider } from './providerPrefs';

interface ChatStudioProps {
  onTraceId?: (traceId: string) => void;
}

interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  text: string;
  traceId?: string;
  blocked?: boolean;
}

export function ChatStudio({ onTraceId }: ChatStudioProps) {
  const [personas, setPersonas] = useState<MiaosPersonaManifest[]>([]);
  const [providers, setProviders] = useState<MiaosProviderInfo[]>([]);
  const [selectedPackageId, setSelectedPackageId] = useState('mia');
  const [selectedProvider, setSelectedProvider] = useState(DEFAULT_PROVIDER);
  const [inputText, setInputText] = useState('Привет, Mia! Кто ты и чем можешь помочь?');
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadStudioData = useCallback(async () => {
    try {
      const [personaList, providerList] = await Promise.all([fetchPersonas(), fetchProviders()]);
      setPersonas(personaList);
      setProviders(providerList);
      if (personaList.length > 0) {
        setSelectedPackageId((prev) =>
          personaList.some((persona) => (persona.package_id || 'mia') === prev)
            ? prev
            : personaList[0].package_id || 'mia',
        );
      }
      setSelectedProvider((prev) => {
        const current = providerList.find((item) => item.name === prev);
        if (current?.available) return prev;
        return pickDefaultProvider(providerList);
      });
    } catch {
      setPersonas([]);
      setProviders([]);
    }
  }, []);

  useEffect(() => {
    void loadStudioData();
  }, [loadStudioData]);

  useEffect(() => {
    const onRefresh = () => void loadStudioData();
    window.addEventListener('miya:studio-refresh', onRefresh);
    return () => window.removeEventListener('miya:studio-refresh', onRefresh);
  }, [loadStudioData]);

  const sendMessage = useCallback(async () => {
    const text = inputText.trim();
    if (!text) return;

    setBusy(true);
    setError(null);
    setMessages((prev) => [...prev, { id: `u-${Date.now()}`, role: 'user', text }]);
    setInputText('');

    try {
      const turn: MiaosChatTurn = await sendChatMessage(text, selectedPackageId, selectedProvider);
      onTraceId?.(turn.trace_id);
      setMessages((prev) => [
        ...prev,
        {
          id: `a-${turn.trace_id}`,
          role: 'assistant',
          text: turn.response_text,
          traceId: turn.trace_id,
          blocked: turn.blocked,
        },
      ]);
      window.dispatchEvent(new CustomEvent('miya:studio-refresh'));
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Не удалось отправить сообщение');
    } finally {
      setBusy(false);
    }
  }, [inputText, onTraceId, selectedPackageId, selectedProvider]);

  const selectedPersona = personas.find(
    (persona) => (persona.package_id || 'mia') === selectedPackageId,
  );

  return (
    <section id="miya-chat-studio" className="miya-chat-studio">
      <div className="miya-run-header">
        <h2 className="miya-run-title">Chat Studio</h2>
        <span className="miya-run-badge">{messages.length} msgs</span>
      </div>

      <p className="miya-run-hint">
        Один ход через <code>POST /chat</code>: persona → PersonalityGuard → провайдер → Policy Gate → audit
        log.
      </p>
      {selectedPersona?.model_binding && (
        <p className="miya-run-hint">
          Persona binding: <code>{selectedPersona.model_binding.provider}</code> /{' '}
          <code>{selectedPersona.model_binding.model_id}</code>
        </p>
      )}

      <div className="miya-chat-controls">
        <label className="miya-field">
          <span>Persona package</span>
          <select
            value={selectedPackageId}
            onChange={(e) => setSelectedPackageId(e.target.value)}
            disabled={busy || personas.length === 0}
          >
            {(personas.length
              ? personas
              : [{ package_id: 'mia', name: 'Mia', persona_id: 'mia' }]
            ).map((persona) => (
              <option key={persona.package_id || persona.persona_id} value={persona.package_id || 'mia'}>
                {persona.name} ({persona.package_id || 'mia'})
              </option>
            ))}
          </select>
        </label>

        <label className="miya-field">
          <span>Провайдер</span>
          <select
            value={selectedProvider}
            onChange={(e) => setSelectedProvider(e.target.value)}
            disabled={busy}
          >
            {(providers.length ? providers : [{ name: 'mock', available: true, description: '' }]).map(
              (item) => (
                <option key={item.name} value={item.name} disabled={!item.available}>
                  {item.name}
                  {item.available ? '' : ' (недоступен)'}
                </option>
              ),
            )}
          </select>
        </label>
      </div>

      {providers.length > 0 && !isMlxAvailable(providers) && (
        <p className="miya-run-hint">
          Для локальной генерации на Apple Silicon перезапустите backend:{' '}
          <code>MIYA_WITH_MLX=1 ~/Documents/miya/frontend/scripts/start-miaos-backend.sh</code>
        </p>
      )}

      {personas.length === 0 && (
        <p className="miya-run-hint">
          Сначала создайте persona в **Persona Studio → Создать Mia**, затем вернитесь сюда.
        </p>
      )}

      {messages.length > 0 && (
        <ol className="miya-chat-log">
          {messages.map((message) => (
            <li
              key={message.id}
              className={`miya-chat-msg miya-chat-msg-${message.role}${message.blocked ? ' miya-chat-msg-blocked' : ''}`}
            >
              <span className="miya-chat-msg-label">
                {message.role === 'user' ? 'Вы' : 'Mia'}
                {message.traceId ? ` · ${message.traceId}` : ''}
              </span>
              <p className="miya-chat-msg-text">{message.text}</p>
            </li>
          ))}
        </ol>
      )}

      <label className="miya-field miya-chat-input">
        <span>Сообщение</span>
        <textarea
          rows={2}
          value={inputText}
          onChange={(e) => setInputText(e.target.value)}
          disabled={busy || personas.length === 0}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) {
              e.preventDefault();
              void sendMessage();
            }
          }}
        />
      </label>

      <div className="miya-run-actions">
        <button
          type="button"
          className="miya-btn miya-btn-primary"
          onClick={() => void sendMessage()}
          disabled={busy || personas.length === 0 || !inputText.trim()}
        >
          {busy ? 'Думаю…' : 'Отправить'}
        </button>
      </div>

      {error && <pre className="miya-run-error">{error}</pre>}
    </section>
  );
}
