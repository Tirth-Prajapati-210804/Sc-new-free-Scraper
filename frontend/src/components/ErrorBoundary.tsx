import { Component, type ErrorInfo, type ReactNode } from "react";

interface Props {
  children: ReactNode;
}

interface State {
  hasError: boolean;
}

export class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = { hasError: false };
  }

  static getDerivedStateFromError(): State {
    return { hasError: true };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error("ErrorBoundary caught:", error, info);
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="flex min-h-[400px] flex-col items-center justify-center gap-4 text-center">
          <p className="text-lg font-semibold text-slate-800">
            Something went wrong.
          </p>
          <p className="text-sm text-slate-500">
            Refresh the page or contact support.
          </p>
          <button
            onClick={() => window.location.reload()}
            className="rounded-lg bg-brand-600 px-4 py-2 text-sm font-medium text-white hover:bg-brand-700"
          >
            Refresh
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}
