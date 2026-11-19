import { Component, lazy, Suspense, type ReactNode } from "react";

const Impl = lazy(() => import("./EChartImpl"));

/** A chart that fails (e.g. no WebGL) must never take the page down with it. */
class ChartBoundary extends Component<
  { height: number; children: ReactNode },
  { failed: boolean }
> {
  state = { failed: false };
  static getDerivedStateFromError() {
    return { failed: true };
  }
  render() {
    if (this.state.failed)
      return (
        <p
          role="status"
          style={{ height: this.props.height }}
          className="flex items-center justify-center text-sm text-slate-500"
        >
          This chart could not be drawn in this browser.
        </p>
      );
    return this.props.children;
  }
}

/**
 * Chart wrapper. ECharts (and the 3D add-on) load on first use, so pages without charts stay light.
 * `label` is a text summary of what the chart shows (screen readers get it instead of the canvas).
 */
export function EChart({
  option,
  height = 280,
  label,
}: {
  option: object;
  height?: number;
  label: string;
}) {
  return (
    <ChartBoundary height={height}>
      <Suspense
        fallback={
          <div
            style={{ height }}
            className="animate-pulse rounded-xl bg-white/5"
            aria-busy="true"
          />
        }
      >
        <Impl option={option} height={height} label={label} />
      </Suspense>
    </ChartBoundary>
  );
}
