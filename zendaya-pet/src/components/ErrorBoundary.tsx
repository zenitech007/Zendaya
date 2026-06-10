import { Component, type ReactNode } from "react";

interface Props {
  children: ReactNode;
  fallbackTitle?: string;
}

interface State {
  error: Error | null;
}

export class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  componentDidCatch(error: Error, info: unknown) {
    // Surface to console too, in case devtools are open.
    // eslint-disable-next-line no-console
    console.error("[ErrorBoundary]", error, info);
  }

  render() {
    if (this.state.error) {
      return (
        <div
          style={{
            position: "absolute",
            inset: 0,
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            justifyContent: "center",
            padding: 24,
            color: "#ffd6d6",
            background: "rgba(40, 0, 0, 0.4)",
            fontFamily:
              "ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace",
            fontSize: 13,
            lineHeight: 1.5,
            textAlign: "left",
            overflow: "auto",
          }}
        >
          <div style={{ fontWeight: 600, marginBottom: 8 }}>
            {this.props.fallbackTitle ?? "Something failed in the UI"}
          </div>
          <pre style={{ whiteSpace: "pre-wrap", wordBreak: "break-word" }}>
            {String(this.state.error?.stack ?? this.state.error)}
          </pre>
        </div>
      );
    }
    return this.props.children;
  }
}
