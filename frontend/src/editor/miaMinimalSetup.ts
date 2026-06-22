import type { Graph } from '@antv/x6';
import {
  checkMiaosHealth,
  createPersona,
  fetchAeonStatus,
  fetchGraphLibrary,
  fetchModels,
  fetchPersonas,
  fetchProviders,
  fetchTemplates,
  registerMiaosModel,
  saveGraphToLibrary,
  instantiateTemplate,
  type MiaosGraphRun,
  type MiaosModelRecord,
  type MiaosPersonaManifest,
  type MiaosProviderInfo,
} from './miaosApi';
import { buildMiaProfile, DEMO_MODELS, MIA_GRAPH_FILENAME } from './demoAssets';
import { importMiaosToCanvas } from './miaosImport';
import { getSelectedRuntimeProfile } from './editorPrefs';
import { isMlxAvailable, pickDefaultProvider } from './providerPrefs';

export interface MiaScenarioStatus {
  online: boolean;
  mlxAvailable: boolean;
  provider: string;
  runtimeProfileSelected: boolean;
  templateRegistryReady: boolean;
  modelsReady: boolean;
  modelCount: number;
  personaReady: boolean;
  libraryReady: boolean;
  canvasReady: boolean;
  runWaitingApproval: boolean;
  runCompleted: boolean;
  aeonOnline: boolean;
  aeonResponded: boolean;
  aeonGoalAdded: boolean;
  aeonConsolidated: boolean;
}

export interface MiaBootstrapResult {
  steps: string[];
  provider: string;
  models: MiaosModelRecord[];
  personas: MiaosPersonaManifest[];
}

function hasMiaPersona(personas: MiaosPersonaManifest[]): boolean {
  return personas.some(
    (persona) => persona.package_id === 'mia' || persona.persona_id.includes('mia'),
  );
}

function hasDemoModels(models: MiaosModelRecord[]): boolean {
  return DEMO_MODELS.every((demo) => models.some((model) => model.repo === demo.repo));
}

export async function fetchMiaScenarioStatus(
  graph: Graph | null,
  lastRun?: MiaosGraphRun | null,
): Promise<MiaScenarioStatus> {
  const online = await checkMiaosHealth();
  let providers: MiaosProviderInfo[] = [];
  let models: MiaosModelRecord[] = [];
  let personas: MiaosPersonaManifest[] = [];
  let libraryReady = false;
  let templateRegistryReady = false;
  let aeonOnline = false;
  let aeonGoalAdded = false;
  let aeonConsolidated = false;

  if (online) {
    const [providerList, modelList, personaList, templates, library, aeonStatus] = await Promise.all([
      fetchProviders(),
      fetchModels(),
      fetchPersonas(),
      fetchTemplates(),
      fetchGraphLibrary(),
      fetchAeonStatus().catch(() => null),
    ]);
    providers = providerList;
    models = modelList;
    personas = personaList;
    templateRegistryReady = templates.some((item) => item.template_id === 'mia-minimal');
    libraryReady = library.some((item) => item.filename === MIA_GRAPH_FILENAME);
    aeonOnline = Boolean(aeonStatus?.available);
    aeonGoalAdded = Boolean(aeonStatus?.active_goals.some((goal) => goal.source === 'user'));
    aeonConsolidated = Boolean(aeonStatus?.skill_hints.some((hint) => hint.includes('morning_consolidation')));
  }

  const provider = pickDefaultProvider(providers);

  return {
    online,
    mlxAvailable: isMlxAvailable(providers),
    provider,
    runtimeProfileSelected: Boolean(getSelectedRuntimeProfile()),
    templateRegistryReady,
    modelsReady: hasDemoModels(models),
    modelCount: models.length,
    personaReady: hasMiaPersona(personas),
    libraryReady,
    canvasReady: Boolean(graph && graph.getNodes().length >= 3),
    runWaitingApproval: lastRun?.status === 'waiting_for_approval',
    runCompleted: lastRun?.status === 'completed',
    aeonOnline,
    aeonResponded: Boolean(
      typeof sessionStorage !== 'undefined' && sessionStorage.getItem('miya:aeon-responded') === '1',
    ),
    aeonGoalAdded,
    aeonConsolidated,
  };
}

export async function bootstrapMiaMinimal(
  graph: Graph | null,
  options?: { replaceCanvas?: boolean },
): Promise<MiaBootstrapResult> {
  const online = await checkMiaosHealth();
  if (!online) {
    throw new Error('Backend MiaOS недоступен — запустите start-miaos-backend.sh');
  }

  const steps: string[] = [];
  const providers = await fetchProviders();
  const provider = pickDefaultProvider(providers);

  let models = await fetchModels();
  for (const payload of DEMO_MODELS) {
    if (models.some((model) => model.repo === payload.repo)) continue;
    await registerMiaosModel(payload);
    steps.push(`Модель ${payload.repo}`);
  }
  if (steps.some((step) => step.startsWith('Модель'))) {
    models = await fetchModels();
  }

  let personas = await fetchPersonas();
  if (!hasMiaPersona(personas)) {
    await createPersona('Mia', buildMiaProfile(provider), 'mia');
    personas = await fetchPersonas();
    steps.push(`Persona Mia (${provider})`);
  }

  if (graph) {
    const shouldLoadTemplate =
      graph.getNodes().length === 0 || options?.replaceCanvas === true;
    if (shouldLoadTemplate) {
      const spec = await instantiateTemplate('mia-minimal');
      importMiaosToCanvas(graph, spec);
      steps.push('Template Registry → Mia Minimal на холсте');
    }
  }

  const library = await fetchGraphLibrary();
  if (!library.some((item) => item.filename === MIA_GRAPH_FILENAME)) {
    const spec = await instantiateTemplate('mia-minimal');
    await saveGraphToLibrary(spec, MIA_GRAPH_FILENAME);
    steps.push(`Graph Library → ${MIA_GRAPH_FILENAME}`);
  }

  if (steps.length === 0) {
    steps.push('Всё уже готово — можно переходить к чату и запуску графа');
  }

  window.dispatchEvent(new CustomEvent('miya:studio-refresh'));

  return { steps, provider, models, personas };
}

export function scrollToPanel(elementId: string) {
  const targetTabs: Record<string, string> = {
    'miya-runtime-profile': 'models',
    'miya-template-registry': 'graph',
    'miya-run-console': 'graph',
    'miya-approval-queue': 'aeon',
    'miya-chat-studio': 'memory',
    'miya-aeon-studio': 'aeon',
  };
  const tab = targetTabs[elementId];
  if (tab) {
    window.dispatchEvent(new CustomEvent('miya:navigate', { detail: { tab, target: elementId } }));
    return;
  }
  document.getElementById(elementId)?.scrollIntoView({ behavior: 'smooth', block: 'start' });
}
