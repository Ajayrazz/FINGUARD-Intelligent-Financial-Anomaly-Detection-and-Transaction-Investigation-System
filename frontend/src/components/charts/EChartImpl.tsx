import {
  BarChart,
  FunnelChart,
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
    const o = reduce
      ? { ...(option as Record<string, unknown>), animation: false }
      : option;
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
