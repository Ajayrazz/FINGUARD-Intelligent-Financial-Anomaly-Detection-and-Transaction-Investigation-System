import {
  BarChart,
  FunnelChart,
  GaugeChart,
  LineChart,
  PictorialBarChart,
  PieChart,
  RadarChart,
  TreemapChart,
} from "echarts/charts";
import {
  GridComponent,
  LegendComponent,
  MarkPointComponent,
  PolarComponent,
  RadarComponent,
  TooltipComponent,
  VisualMapComponent,
} from "echarts/components";
import * as echarts from "echarts/core";
import { CanvasRenderer } from "echarts/renderers";
import {
  Bar3DChart,
  Line3DChart,
  Scatter3DChart,
  SurfaceChart,
} from "echarts-gl/charts";
import { Grid3DComponent } from "echarts-gl/components";
import { useEffect, useRef } from "react";

echarts.use([
  GaugeChart,
  FunnelChart,
  PictorialBarChart,
  TreemapChart,
  MarkPointComponent,
  PolarComponent,
  SurfaceChart,
  BarChart,
  LineChart,
  PieChart,
  RadarChart,
  GridComponent,
  LegendComponent,
  RadarComponent,
  TooltipComponent,
  VisualMapComponent,
  CanvasRenderer,
  Bar3DChart,
  Scatter3DChart,
  Line3DChart,
  Grid3DComponent,
]);

/** Shared look: transparent canvas on the glass panels, indigo/violet/cyan palette, light text. */
export const PALETTE = [
  "#818cf8",
  "#a78bfa",
  "#22d3ee",
  "#f472b6",
  "#fbbf24",
  "#34d399",
];
echarts.registerTheme("finguard", {
  color: PALETTE,
  backgroundColor: "transparent",
  textStyle: { color: "#b8bde0", fontFamily: "Inter, system-ui, sans-serif" },
  tooltip: {
    backgroundColor: "rgba(14,15,34,0.92)",
    borderColor: "rgba(129,140,248,0.4)",
    textStyle: { color: "#e4e7f7" },
  },
  legend: { textStyle: { color: "#b8bde0" } },
});

/**
 * echarts-gl's supersampling and post effects build shaders with `new Function`, which a strict Content-Security-Policy
 * (script-src 'self', no unsafe-eval; see docker/caddy/Caddyfile) rightly blocks. Turning them off keeps every 3D chart
 * working without weakening the policy; the only loss is the extra anti-aliasing on a still chart.
 */
function withoutEval(option: object): object {
  const o = option as Record<string, unknown>;
  if (!o.grid3D) return option;
  const fix = (g: unknown) => ({
    ...(g as object),
    temporalSuperSampling: { enable: false },
    postEffect: { enable: false },
  });
  return {
    ...o,
    grid3D: Array.isArray(o.grid3D) ? o.grid3D.map(fix) : fix(o.grid3D),
  };
}

export default function EChartImpl({
  option,
  height,
  label,
}: {
  option: object;
  height: number;
  label: string;
}) {
  const el = useRef<HTMLDivElement>(null);
  const chart = useRef<echarts.ECharts | null>(null);

  useEffect(() => {
    if (!el.current) return;
    const c = echarts.init(el.current, "finguard", { renderer: "canvas" });
    chart.current = c;
    const ro = new ResizeObserver(() => c.resize());
    ro.observe(el.current);
    return () => {
      ro.disconnect();
      c.dispose();
      chart.current = null;
    };
  }, []);

  useEffect(() => {
    const reduce =
      window.matchMedia?.("(prefers-reduced-motion: reduce)").matches ?? false;
    const safe = withoutEval(option);
    const o = reduce
      ? { ...(safe as Record<string, unknown>), animation: false }
      : safe;
    chart.current?.setOption(o as echarts.EChartsCoreOption, true);
  }, [option]);

  return (
    <div
      ref={el}
      role="img"
      aria-label={label}
      style={{ height, width: "100%" }}
    />
  );
}
