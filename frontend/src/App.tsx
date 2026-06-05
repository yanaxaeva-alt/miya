import './App.css'
import type { ReactNode } from 'react'
import { useEffect, useMemo, useState } from 'react'
import GraphStudio from './GraphStudio'

type ApiHealth = {
  status: string
}

type RuntimeProfile = {
  name: string
  role: string
  max_context_tokens_default: number
  always_busy: boolean | 'guarded'
}

type ModelRecord = {
  id: string
  repo: string
  pool_role?: string | null
  status: string
}

const API_BASE_URL = import.meta.env.VITE_MIAOS_API_URL ?? 'http://127.0.0.1:8000'

const pages = [
  'Model Studio',
  'Persona Studio',
  'Graph Studio',
  'Run Console',
  'Trace Viewer',
  'Approval Queue',
] as const

type PageName = (typeof pages)[number]

async function fetchJson<T>(path: string): Promise<T | null> {
  try {
    const response = await fetch(`${API_BASE_URL}${path}`)
    if (!response.ok) {
      return null
    }
    return (await response.json()) as T
  } catch {
    return null
  }
}

function App() {
  const [activePage, setActivePage] = useState<PageName>('Model Studio')
  const [health, setHealth] = useState<ApiHealth | null>(null)
  const [profiles, setProfiles] = useState<RuntimeProfile[]>([])
  const [models, setModels] = useState<ModelRecord[]>([])

  useEffect(() => {
    void fetchJson<ApiHealth>('/health').then(setHealth)
    void fetchJson<RuntimeProfile[]>('/runtime/profiles').then((data) => {
      setProfiles(data ?? [])
    })
    void fetchJson<ModelRecord[]>('/models').then((data) => {
      setModels(data ?? [])
    })
  }, [])

  const backendStatus = health?.status === 'ok' ? 'connected' : 'offline'
  const activePanel = useMemo(
    () => renderPanel(activePage, profiles, models, backendStatus),
    [activePage, profiles, models, backendStatus],
  )

  return (
    <main className="app-shell">
      <aside className="sidebar" aria-label="MiaOS navigation">
        <div className="brand">
          <span className="brand-mark">M</span>
          <div>
            <strong>MiaOS Builder</strong>
            <small>developer preview</small>
          </div>
        </div>
        <nav>
          {pages.map((page) => (
            <button
              className={page === activePage ? 'nav-item active' : 'nav-item'}
              key={page}
              onClick={() => setActivePage(page)}
              type="button"
            >
              {page}
            </button>
          ))}
        </nav>
        <div className={`status ${backendStatus}`}>
          <span></span>
          Backend {backendStatus}
        </div>
      </aside>

      <section className="workspace">
        <header className="workspace-header">
          <div>
            <p className="eyebrow">Runtime-first editor skeleton</p>
            <h1>{activePage}</h1>
          </div>
          <div className="local-badge">Local API · {API_BASE_URL}</div>
        </header>
        {activePanel}
      </section>
    </main>
  )
}

function renderPanel(
  page: PageName,
  profiles: RuntimeProfile[],
  models: ModelRecord[],
  backendStatus: string,
) {
  switch (page) {
    case 'Model Studio':
      return (
        <section className="panel-grid">
          <InfoCard title="Runtime profiles" value={profiles.length.toString()}>
            {profiles.map((profile) => (
              <div className="data-row" key={profile.name}>
                <span>{profile.name}</span>
                <small>
                  {profile.max_context_tokens_default.toLocaleString()} ctx · always-busy{' '}
                  {String(profile.always_busy)}
                </small>
              </div>
            ))}
          </InfoCard>
          <InfoCard title="Registered models" value={models.length.toString()}>
            {models.length === 0 ? (
              <p>No model metadata registered yet.</p>
            ) : (
              models.map((model) => (
                <div className="data-row" key={model.id}>
                  <span>{model.repo}</span>
                  <small>
                    {model.pool_role ?? 'unassigned'} · {model.status}
                  </small>
                </div>
              ))
            )}
          </InfoCard>
        </section>
      )
    case 'Persona Studio':
      return (
        <Placeholder
          title="Persona packages"
          text="Create, validate, import, and export minimal .mia packages backed by the runtime persona API."
        />
      )
    case 'Graph Studio':
      return <GraphStudio apiBaseUrl={API_BASE_URL} />
    case 'Run Console':
      return (
        <Placeholder
          title="Run events"
          text="Graph and chat runs will stream here from the local WebSocket event API."
        />
      )
    case 'Trace Viewer':
      return (
        <Placeholder
          title="Trace and audit"
          text="Trace IDs, policy decisions, and decisions.jsonl evidence will be browsable here."
        />
      )
    case 'Approval Queue':
      return (
        <Placeholder
          title="Human approval boundary"
          text="Publish, send, delete, and write-outside-sandbox requests stop here before execution."
        />
      )
    default:
      return <Placeholder title="Unknown page" text={`Backend is ${backendStatus}.`} />
  }
}

function InfoCard({
  children,
  title,
  value,
}: {
  children: ReactNode
  title: string
  value: string
}) {
  return (
    <article className="card">
      <div className="card-heading">
        <h2>{title}</h2>
        <strong>{value}</strong>
      </div>
      <div className="card-body">{children}</div>
    </article>
  )
}

function Placeholder({ title, text }: { title: string; text: string }) {
  return (
    <article className="placeholder">
      <h2>{title}</h2>
      <p>{text}</p>
    </article>
  )
}

export default App
