import { useCallback, useEffect, useState } from 'react';
import {
  addDomainNote,
  deleteDomainNote,
  deleteMemoryEpisode,
  fetchDomainNotes,
  fetchMemoryEpisodes,
  fetchMemorySummary,
  fetchProfileFacts,
  upsertProfileFact,
  type MiaosDomainNote,
  type MiaosMemoryEpisode,
  type MiaosMemorySummary,
  type MiaosProfileFact,
} from './miaosApi';

function formatTs(ts: string) {
  try {
    return new Date(ts).toLocaleString();
  } catch {
    return ts;
  }
}

export function MemoryStudio() {
  const [summary, setSummary] = useState<MiaosMemorySummary | null>(null);
  const [episodes, setEpisodes] = useState<MiaosMemoryEpisode[]>([]);
  const [facts, setFacts] = useState<MiaosProfileFact[]>([]);
  const [notes, setNotes] = useState<MiaosDomainNote[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [factKey, setFactKey] = useState('locale');
  const [factValue, setFactValue] = useState('ru-RU');
  const [noteDomain, setNoteDomain] = useState('general');
  const [noteContent, setNoteContent] = useState('');

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [summaryData, episodeList, factList, noteList] = await Promise.all([
        fetchMemorySummary('mia'),
        fetchMemoryEpisodes('mia'),
        fetchProfileFacts('mia'),
        fetchDomainNotes('mia'),
      ]);
      setSummary(summaryData);
      setEpisodes(episodeList);
      setFacts(factList);
      setNotes(noteList);
    } catch (err) {
      setSummary(null);
      setEpisodes([]);
      setFacts([]);
      setNotes([]);
      setError(err instanceof Error ? err.message : 'Не удалось загрузить Memory');
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
    <section id="miya-memory-studio" className="miya-memory-studio">
      <div className="miya-run-header">
        <h2 className="miya-run-title">Memory Studio</h2>
        <span className="miya-run-badge">{summary?.episodes ?? 0} episodes</span>
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
        Memory MVP в SQLite: episodic log, profile facts, domain notes, deletion logging. Chat Studio
        автоматически пишет эпизоды после каждого хода.
      </p>

      {summary && (
        <p className="miya-run-hint">
          episodes {summary.episodes} · facts {summary.profile_facts} · notes {summary.domain_notes}{' '}
          · deletions logged {summary.deletions_logged}
        </p>
      )}

      {error && <pre className="miya-run-error">{error}</pre>}

      <div className="miya-memory-grid">
        <div className="miya-memory-panel">
          <h3 className="miya-trace-section-title">Episodic memory</h3>
          {episodes.length === 0 && <p className="miya-run-hint">Пока пусто — напишите в Chat Studio.</p>}
          <ul className="miya-memory-list">
            {episodes.map((episode) => (
              <li key={episode.id} className="miya-memory-item">
                <div className="miya-memory-item-head">
                  <code>{episode.role}</code>
                  <span>{formatTs(episode.created_at)}</span>
                  <button
                    type="button"
                    className="miya-btn miya-btn-secondary"
                    onClick={() => void deleteMemoryEpisode(episode.id).then(() => refresh())}
                  >
                    Удалить
                  </button>
                </div>
                <p className="miya-memory-item-text">{episode.content}</p>
                {episode.tags.length > 0 && (
                  <p className="miya-model-id">
                    tags: {episode.tags.map((tag) => (
                      <code key={tag}>{tag}</code>
                    ))}
                  </p>
                )}
              </li>
            ))}
          </ul>
        </div>

        <div className="miya-memory-panel">
          <h3 className="miya-trace-section-title">Profile facts</h3>
          <div className="miya-graph-save-row">
            <label className="miya-field miya-graph-save-field">
              <span>Ключ</span>
              <input value={factKey} onChange={(e) => setFactKey(e.target.value)} />
            </label>
            <label className="miya-field miya-graph-save-field">
              <span>Значение</span>
              <input value={factValue} onChange={(e) => setFactValue(e.target.value)} />
            </label>
            <button
              type="button"
              className="miya-btn"
              onClick={() =>
                void upsertProfileFact(factKey.trim(), factValue.trim())
                  .then(() => refresh())
                  .catch((err) =>
                    setError(err instanceof Error ? err.message : 'Не удалось сохранить fact'),
                  )
              }
            >
              Сохранить
            </button>
          </div>
          <ul className="miya-memory-list">
            {facts.map((fact) => (
              <li key={fact.id} className="miya-memory-item">
                <strong>{fact.key}</strong> = {fact.value}
              </li>
            ))}
          </ul>
        </div>

        <div className="miya-memory-panel">
          <h3 className="miya-trace-section-title">Domain notes</h3>
          <div className="miya-graph-save-row">
            <label className="miya-field miya-graph-save-field">
              <span>Domain</span>
              <input value={noteDomain} onChange={(e) => setNoteDomain(e.target.value)} />
            </label>
            <label className="miya-field miya-graph-save-field">
              <span>Заметка</span>
              <input value={noteContent} onChange={(e) => setNoteContent(e.target.value)} />
            </label>
            <button
              type="button"
              className="miya-btn"
              onClick={() => {
                const content = noteContent.trim();
                if (!content) return;
                void addDomainNote(noteDomain.trim() || 'general', content)
                  .then(() => {
                    setNoteContent('');
                    return refresh();
                  })
                  .catch((err) =>
                    setError(err instanceof Error ? err.message : 'Не удалось сохранить note'),
                  );
              }}
            >
              Добавить
            </button>
          </div>
          <ul className="miya-memory-list">
            {notes.map((note) => (
              <li key={note.id} className="miya-memory-item">
                <div className="miya-memory-item-head">
                  <code>{note.domain}</code>
                  <button
                    type="button"
                    className="miya-btn miya-btn-secondary"
                    onClick={() => void deleteDomainNote(note.id).then(() => refresh())}
                  >
                    Удалить
                  </button>
                </div>
                <p className="miya-memory-item-text">{note.content}</p>
              </li>
            ))}
          </ul>
        </div>
      </div>
    </section>
  );
}
