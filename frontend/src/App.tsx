import { lazy, Suspense, useEffect, useState, type ReactNode } from 'react';
import type { Graph } from '@antv/x6';
import { checkMiaosHealth, type MiaosGraphRun, type MiaosModelRecord } from './editor/miaosApi';
import { setStatus } from './miyaBridge';

type AppTab = 'overview' | 'aeon' | 'graph' | 'memory' | 'models' | 'quality';

const TABS: Array<{ id: AppTab; label: string; description: string }> = [
  { id: 'overview', label: 'Overview', description: 'первый запуск и быстрые переходы' },
  { id: 'aeon', label: 'AEON', description: 'ask, goals, heartbeat, acceptance' },
  { id: 'graph', label: 'Graph Builder', description: 'холст, запуск, templates' },
  { id: 'memory', label: 'Memory', description: 'память и чат' },
  { id: 'models', label: 'Models & Persona', description: 'профиль железа, модели, persona' },
  { id: 'quality', label: 'Quality & Tools', description: 'tools, evals, traces' },
];

const SimpleGraph = lazy(() => import('./editor/SimpleGraph').then((module) => ({ default: module.SimpleGraph })));
const RunConsole = lazy(() => import('./editor/RunConsole').then((module) => ({ default: module.RunConsole })));
const TraceViewer = lazy(() => import('./editor/TraceViewer').then((module) => ({ default: module.TraceViewer })));
const ApprovalQueue = lazy(() => import('./editor/ApprovalQueue').then((module) => ({ default: module.ApprovalQueue })));
const ModelStudio = lazy(() => import('./editor/ModelStudio').then((module) => ({ default: module.ModelStudio })));
const PersonaStudio = lazy(() => import('./editor/PersonaStudio').then((module) => ({ default: module.PersonaStudio })));
const MemoryStudio = lazy(() => import('./editor/MemoryStudio').then((module) => ({ default: module.MemoryStudio })));
const ChatStudio = lazy(() => import('./editor/ChatStudio').then((module) => ({ default: module.ChatStudio })));
const AeonStudio = lazy(() => import('./editor/AeonStudio').then((module) => ({ default: module.AeonStudio })));
const GraphLibrary = lazy(() => import('./editor/GraphLibrary').then((module) => ({ default: module.GraphLibrary })));
const ToolRegistry = lazy(() => import('./editor/ToolRegistry').then((module) => ({ default: module.ToolRegistry })));
const QualityLab = lazy(() => import('./editor/QualityLab').then((module) => ({ default: module.QualityLab })));
const MiaScenario = lazy(() => import('./editor/MiaScenario').then((module) => ({ default: module.MiaScenario })));
const WelcomePanel = lazy(() => import('./editor/WelcomePanel').then((module) => ({ default: module.WelcomePanel })));
const RuntimeProfileStudio = lazy(() =>
  import('./editor/RuntimeProfileStudio').then((module) => ({ default: module.RuntimeProfileStudio })),
);
const TemplateRegistry = lazy(() =>
  import('./editor/TemplateRegistry').then((module) => ({ default: module.TemplateRegistry })),
);

function TabIntro({
  title,
  body,
  actions,
}: {
  title: string;
  body: string;
  actions?: ReactNode;
}) {
  return (
    <section className="miya-tab-intro">
      <div>
        <h2>{title}</h2>
        <p>{body}</p>
      </div>
      {actions && <div className="miya-tab-intro-actions">{actions}</div>}
    </section>
  );
}

function AdvancedSection({
  title,
  children,
  open = false,
}: {
  title: string;
  children: ReactNode;
  open?: boolean;
}) {
  return (
    <details className="miya-advanced-section" open={open}>
      <summary>{title}</summary>
      <div className="miya-advanced-section-body">{children}</div>
    </details>
  );
}

function TabLoading() {
  return <div className="miya-tab-loading">Загружаю вкладку…</div>;
}

export default function App() {
  const [graph, setGraph] = useState<Graph | null>(null);
  const [lastTraceId, setLastTraceId] = useState<string | null>(null);
  const [lastRun, setLastRun] = useState<MiaosGraphRun | null>(null);
  const [registeredModels, setRegisteredModels] = useState<MiaosModelRecord[]>([]);
  const [activeTab, setActiveTab] = useState<AppTab>('overview');

  useEffect(() => {
    let alive = true;
    const refreshBackendStatus = async () => {
      const ok = await checkMiaosHealth();
      if (alive) setStatus(ok ? 'Backend MiaOS online' : 'Backend MiaOS offline');
    };
    void refreshBackendStatus();
    const timer = window.setInterval(() => void refreshBackendStatus(), 15000);
    return () => {
      alive = false;
      window.clearInterval(timer);
    };
  }, []);

  useEffect(() => {
    const onNavigate = (event: Event) => {
      const detail = (event as CustomEvent<{ tab?: AppTab; target?: string }>).detail;
      if (!detail?.tab) return;
      setActiveTab(detail.tab);
      if (detail.target) {
        window.setTimeout(() => {
          document.getElementById(detail.target ?? '')?.scrollIntoView({
            behavior: 'smooth',
            block: 'start',
          });
        }, 80);
      }
    };
    window.addEventListener('miya:navigate', onNavigate);
    return () => window.removeEventListener('miya:navigate', onNavigate);
  }, []);

  const runConsole = (
    <RunConsole
      graph={graph}
      syncedRun={lastRun}
      onRunComplete={(run: MiaosGraphRun) => {
        setLastTraceId(run.trace_id);
        setLastRun(run);
      }}
    />
  );

  const approvalQueue = (
    <ApprovalQueue
      lastRun={lastRun}
      onRunUpdate={(run) => {
        setLastRun((prev) =>
          prev
            ? {
                ...run,
                events: [...prev.events, ...run.events],
                outputs: { ...prev.outputs, ...run.outputs },
              }
            : run,
        );
        setLastTraceId(run.trace_id);
      }}
    />
  );

  const traceViewer = <TraceViewer traceId={lastTraceId} run={lastRun} />;

  return (
    <main className="miya-shell">
      <nav className="miya-tabs" aria-label="Рабочие зоны Miya Editor">
        {TABS.map((tab) => (
          <button
            key={tab.id}
            type="button"
            className={`miya-tab${activeTab === tab.id ? ' miya-tab-active' : ''}`}
            onClick={() => setActiveTab(tab.id)}
            aria-current={activeTab === tab.id ? 'page' : undefined}
          >
            <span className="miya-tab-label">{tab.label}</span>
            <span className="miya-tab-description">{tab.description}</span>
          </button>
        ))}
      </nav>

      <section className="miya-tab-panel" aria-live="polite">
        <Suspense fallback={<TabLoading />}>
          {activeTab === 'overview' && (
            <div className="miya-tab-stack">
              <TabIntro
                title="Главная"
                body="Выберите, что хотите сделать сейчас. Подробный checklist спрятан ниже, чтобы не мешать работе."
              />
              <section className="miya-start-cards" aria-label="Основные действия">
                <button type="button" className="miya-start-card miya-start-card-primary" onClick={() => setActiveTab('aeon')}>
                  <span>1</span>
                  <strong>Работать с AEON</strong>
                  <em>Спросить Мию, добавить цель, выполнить consolidation.</em>
                </button>
                <button type="button" className="miya-start-card" onClick={() => setActiveTab('graph')}>
                  <span>2</span>
                  <strong>Собрать graph</strong>
                  <em>Открыть холст, шаблоны и Run Console.</em>
                </button>
                <button type="button" className="miya-start-card" onClick={() => setActiveTab('models')}>
                  <span>3</span>
                  <strong>Проверить настройки</strong>
                  <em>Runtime profile, модели и persona package.</em>
                </button>
              </section>
              <AdvancedSection title="Setup checklist">
                <WelcomePanel />
              </AdvancedSection>
            </div>
          )}

          {activeTab === 'aeon' && (
            <div className="miya-tab-stack">
            <TabIntro
              title="AEON"
              body="Основной сценарий: спросить Мию, добавить цель, выполнить consolidation. Остальное спрятано справа как контроль и аудит."
              actions={
                <>
                  <button
                    type="button"
                    className="miya-btn miya-btn-primary"
                    onClick={() => document.getElementById('miya-aeon-studio')?.scrollIntoView({ behavior: 'smooth' })}
                  >
                    Спросить AEON
                  </button>
                  <button
                    type="button"
                    className="miya-btn"
                    onClick={() => document.getElementById('miya-scenario')?.scrollIntoView({ behavior: 'smooth' })}
                  >
                    Checklist
                  </button>
                </>
              }
            />
            <div className="miya-workspace-grid miya-workspace-grid-aeon">
              <div className="miya-workspace-main">
                <AeonStudio onTraceId={setLastTraceId} />
              </div>
              <aside className="miya-workspace-side">
                <MiaScenario graph={graph} lastRun={lastRun} onModelsChange={setRegisteredModels} compact />
                <AdvancedSection title="Approval Queue">{approvalQueue}</AdvancedSection>
                <AdvancedSection title="Trace Viewer">{traceViewer}</AdvancedSection>
              </aside>
            </div>
            </div>
          )}

          {activeTab === 'graph' && (
            <div className="miya-tab-stack">
            <TabIntro
              title="Graph Builder"
              body="Одна зона для визуального графа: соберите узлы на холсте, затем запустите через Run Console. Templates и Library спрятаны ниже."
              actions={
                <>
                  <button
                    type="button"
                    className="miya-btn miya-btn-primary"
                    onClick={() => document.getElementById('miya-graph-studio')?.scrollIntoView({ behavior: 'smooth' })}
                  >
                    К холсту
                  </button>
                  <button
                    type="button"
                    className="miya-btn"
                    onClick={() => document.getElementById('miya-run-console')?.scrollIntoView({ behavior: 'smooth' })}
                  >
                    К запуску
                  </button>
                </>
              }
            />
            <SimpleGraph onGraphReady={setGraph} registeredModels={registeredModels} lastRun={lastRun} />
            {runConsole}
            <AdvancedSection title="Templates and Library">
              <div className="miya-workspace-grid">
                <TemplateRegistry graph={graph} />
                <GraphLibrary graph={graph} />
              </div>
            </AdvancedSection>
            </div>
          )}

          {activeTab === 'memory' && (
            <div className="miya-tab-stack">
            <TabIntro
              title="Memory"
              body="Сначала обычный чат, затем просмотр эпизодов и заметок памяти. Так проще проверить, что Мия запоминает."
              actions={
                <button
                  type="button"
                  className="miya-btn miya-btn-primary"
                  onClick={() => document.getElementById('miya-chat-studio')?.scrollIntoView({ behavior: 'smooth' })}
                >
                  Открыть чат
                </button>
              }
            />
            <ChatStudio onTraceId={setLastTraceId} />
            <AdvancedSection title="Memory Store">
              <MemoryStudio />
            </AdvancedSection>
            </div>
          )}

          {activeTab === 'models' && (
            <div className="miya-tab-stack">
            <TabIntro
              title="Models & Persona"
              body="Настройка окружения: выберите профиль железа, проверьте модели и persona Mia. Обычно это делается один раз."
            />
            <RuntimeProfileStudio />
            <ModelStudio models={registeredModels} onModelsChange={setRegisteredModels} />
            <AdvancedSection title="Persona Package">
              <PersonaStudio />
            </AdvancedSection>
            </div>
          )}

          {activeTab === 'quality' && (
            <div className="miya-tab-stack">
            <TabIntro
              title="Quality & Tools"
              body="Диагностика и проверка качества. Основной блок — Quality Lab; инструменты и trace доступны как advanced."
            />
            <QualityLab />
            <AdvancedSection title="Tools">
              <ToolRegistry />
            </AdvancedSection>
            <AdvancedSection title="Trace Viewer">{traceViewer}</AdvancedSection>
            </div>
          )}
        </Suspense>
      </section>
    </main>
  );
}
