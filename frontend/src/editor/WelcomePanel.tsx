import { useCallback, useEffect, useState } from 'react';
import { checkMiaosHealth, checkAeonHealth, fetchModels, fetchPersonas, fetchTemplates } from './miaosApi';
import {
  dismissWelcome,
  getSelectedRuntimeProfile,
  isWelcomeDismissed,
  showWelcomeAgain,
} from './editorPrefs';

type SetupStep = {
  id: string;
  label: string;
  target: string;
  done: boolean;
};

function scrollToSection(target: string) {
  const targetTabs: Record<string, string> = {
    'miya-runtime-profile': 'models',
    'miya-persona-studio': 'models',
    'miya-template-registry': 'graph',
    'miya-model-studio': 'models',
    'miya-aeon-studio': 'aeon',
    'miya-scenario': 'aeon',
  };
  const tab = targetTabs[target];
  if (tab) {
    window.dispatchEvent(new CustomEvent('miya:navigate', { detail: { tab, target } }));
    return;
  }
  document.getElementById(target)?.scrollIntoView({ behavior: 'smooth', block: 'start' });
}

export function WelcomePanel() {
  const [visible, setVisible] = useState(() => !isWelcomeDismissed());
  const [backendOk, setBackendOk] = useState(false);
  const [profileSelected, setProfileSelected] = useState(() => Boolean(getSelectedRuntimeProfile()));
  const [templatesReady, setTemplatesReady] = useState(false);
  const [modelsReady, setModelsReady] = useState(false);
  const [personaReady, setPersonaReady] = useState(false);
  const [aeonReady, setAeonReady] = useState(false);

  const refreshStatus = useCallback(async () => {
    const health = await checkMiaosHealth();
    setBackendOk(health);
    setProfileSelected(Boolean(getSelectedRuntimeProfile()));
    if (health) {
      try {
        const [personas, templates, models] = await Promise.all([
          fetchPersonas(),
          fetchTemplates(),
          fetchModels(),
        ]);
        setPersonaReady(personas.length > 0);
        setAeonReady(await checkAeonHealth());
        setTemplatesReady(templates.some((template) => template.template_id === 'mia-minimal'));
        setModelsReady(models.length > 0);
      } catch {
        setPersonaReady(false);
        setAeonReady(false);
        setTemplatesReady(false);
        setModelsReady(false);
      }
    } else {
      setPersonaReady(false);
      setAeonReady(false);
      setTemplatesReady(false);
      setModelsReady(false);
    }
  }, []);

  useEffect(() => {
    void refreshStatus();
  }, [refreshStatus]);

  useEffect(() => {
    const onRefresh = () => void refreshStatus();
    const onWelcomeDismissed = () => setVisible(false);
    const onWelcomeShown = () => setVisible(true);
    window.addEventListener('miya:studio-refresh', onRefresh);
    window.addEventListener('miya:runtime-profile-changed', onRefresh);
    window.addEventListener('miya:welcome-dismissed', onWelcomeDismissed);
    window.addEventListener('miya:welcome-shown', onWelcomeShown);
    return () => {
      window.removeEventListener('miya:studio-refresh', onRefresh);
      window.removeEventListener('miya:runtime-profile-changed', onRefresh);
      window.removeEventListener('miya:welcome-dismissed', onWelcomeDismissed);
      window.removeEventListener('miya:welcome-shown', onWelcomeShown);
    };
  }, [refreshStatus]);

  const steps: SetupStep[] = [
    {
      id: 'backend',
      label: 'Backend MiaOS доступен (порт 8000)',
      target: 'miya-runtime-profile',
      done: backendOk,
    },
    {
      id: 'profile',
      label: 'Выбран runtime profile под ваше железо',
      target: 'miya-runtime-profile',
      done: profileSelected,
    },
    {
      id: 'persona',
      label: 'Создан или импортирован persona package (.mia)',
      target: 'miya-persona-studio',
      done: personaReady,
    },
    {
      id: 'templates',
      label: 'Template Registry доступен и содержит Mia Minimal',
      target: 'miya-template-registry',
      done: templatesReady,
    },
    {
      id: 'models',
      label: 'Model Studio содержит локальные/демо-модели',
      target: 'miya-model-studio',
      done: modelsReady,
    },
    {
      id: 'aeon',
      label: 'AEON Studio отвечает на /aeon/status',
      target: 'miya-aeon-studio',
      done: aeonReady,
    },
    {
      id: 'graph',
      label: 'Пройдите сценарий v1.0 acceptance',
      target: 'miya-scenario',
      done: false,
    },
  ];

  const completedCount = steps.filter((step) => step.done).length;

  if (!visible) {
    return (
      <section className="miya-welcome-collapsed">
        <button type="button" className="miya-btn miya-btn-secondary" onClick={showWelcomeAgain}>
          Показать мастер настройки v1.0
        </button>
      </section>
    );
  }

  return (
    <section id="miya-welcome" className="miya-welcome">
      <div className="miya-run-header">
        <h2 className="miya-run-title">Добро пожаловать в v1.0</h2>
        <span className="miya-run-badge">
          {completedCount}/{steps.length} шагов
        </span>
        <button
          type="button"
          className="miya-btn miya-btn-secondary"
          onClick={() => void refreshStatus()}
        >
          Проверить
        </button>
        <button
          type="button"
          className="miya-btn"
          onClick={() => {
            dismissWelcome();
            setVisible(false);
          }}
        >
          Скрыть
        </button>
      </div>

      <p className="miya-run-hint">
        Мастер первого запуска для локальной v1.0: профиль железа, templates, модели, persona
        package, граф и run. Большинство шагов проверяются автоматически.
      </p>

      <ol className="miya-welcome-steps">
        {steps.map((step, index) => (
          <li
            key={step.id}
            className={`miya-scenario-step${step.done ? ' miya-scenario-step-done' : ''}`}
          >
            <span className="miya-scenario-step-mark">{step.done ? '✓' : index + 1}</span>
            <span className="miya-scenario-step-label">{step.label}</span>
            <button
              type="button"
              className="miya-btn miya-btn-secondary miya-scenario-step-btn"
              onClick={() => scrollToSection(step.target)}
            >
              Перейти
            </button>
          </li>
        ))}
      </ol>
    </section>
  );
}
