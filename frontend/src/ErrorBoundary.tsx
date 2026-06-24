import { Component, type ErrorInfo, type ReactNode } from 'react';

interface Props {
  children: ReactNode;
}

interface State {
  error: Error | null;
}

export class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error) {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error('Miya Editor error:', error, info);
  }

  render() {
    if (this.state.error) {
      return (
        <div
          style={{
            margin: 20,
            padding: 20,
            background: '#FEE2E2',
            border: '2px solid #DC2626',
            borderRadius: 8,
            color: '#991B1B',
            textAlign: 'left',
          }}
        >
          <h2 style={{ marginTop: 0 }}>Ошибка в редакторе</h2>
          <pre style={{ whiteSpace: 'pre-wrap', fontSize: 13 }}>{this.state.error.message}</pre>
          <p>Откройте Safari → Разработка → Показать веб-инспектор → вкладка «Консоль».</p>
        </div>
      );
    }
    return this.props.children;
  }
}
