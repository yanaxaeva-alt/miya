const RUNTIME_PROFILE_KEY = 'miya-runtime-profile';
const WELCOME_DISMISSED_KEY = 'miya-welcome-dismissed';

export function getSelectedRuntimeProfile(): string | null {
  try {
    return localStorage.getItem(RUNTIME_PROFILE_KEY);
  } catch {
    return null;
  }
}

export function setSelectedRuntimeProfile(name: string) {
  localStorage.setItem(RUNTIME_PROFILE_KEY, name);
  window.dispatchEvent(new CustomEvent('miya:runtime-profile-changed', { detail: { name } }));
}

export function isWelcomeDismissed(): boolean {
  try {
    return localStorage.getItem(WELCOME_DISMISSED_KEY) === '1';
  } catch {
    return false;
  }
}

export function dismissWelcome() {
  localStorage.setItem(WELCOME_DISMISSED_KEY, '1');
  window.dispatchEvent(new CustomEvent('miya:welcome-dismissed'));
}

export function showWelcomeAgain() {
  localStorage.removeItem(WELCOME_DISMISSED_KEY);
  window.dispatchEvent(new CustomEvent('miya:welcome-shown'));
}
