/** Parametric surface for one slice of a 3D pie/donut (echarts-gl "surface" series). */
function slice(startRatio: number, endRatio: number, k: number, h: number) {
  const a0 = startRatio * Math.PI * 2;
  const a1 = endRatio * Math.PI * 2;
  const pick = (u: number) => (u < a0 ? a0 : u > a1 ? a1 : u);
  return {
    u: { min: -Math.PI, max: Math.PI * 3, step: Math.PI / 32 },
    v: { min: 0, max: Math.PI * 2, step: Math.PI / 20 },
    x: (u: number, v: number) => Math.cos(pick(u)) * (1 + Math.cos(v) * k),
    y: (u: number, v: number) => Math.sin(pick(u)) * (1 + Math.cos(v) * k),
    z: (u: number, v: number) => {
      if (u < -Math.PI * 0.5) return Math.sin(u);
      if (u > Math.PI * 2.5) return Math.sin(u) * h * 0.1;
      return Math.sin(v) > 0 ? h * 0.1 : -1;
    },
  };
}

/** Rotating 3D donut: one extruded slice per item. `k` is the tube thickness, `h` the slice height. */
export function pie3dOption(
  items: { name: string; value: number; color: string }[],
  opts: { k?: number; h?: number } = {},
) {
  const k = opts.k ?? 0.22;
  const h = opts.h ?? 8;
  const total = items.reduce((s, i) => s + i.value, 0) || 1;
  let acc = 0;
  const series = items.map((it) => {
    const start = acc / total;
    acc += it.value;
    const end = acc / total;
    return {
      name: it.name,
      type: "surface",
      parametric: true,
      wireframe: { show: false },
      shading: "lambert",
      itemStyle: { color: it.color, opacity: 0.96 },
      parametricEquation: slice(start, end >= 1 ? 0.99999 : end, k, h),
    };
  });
  const axis = { show: false, type: "value", min: -2, max: 2 };
  return {
    tooltip: { formatter: (p: { seriesName: string }) => p.seriesName },
    xAxis3D: axis,
    yAxis3D: axis,
    zAxis3D: { show: false, type: "value", min: -1, max: 2 },
    grid3D: {
      show: false,
      boxHeight: 14,
      environment: "none",
      light: {
        main: { intensity: 1.5, alpha: 40, beta: 20 },
        ambient: { intensity: 0.5 },
      },
      viewControl: {
        autoRotate: true,
        autoRotateSpeed: 14,
        distance: 120,
        alpha: 32,
        beta: 10,
        zoomSensitivity: 0,
        panSensitivity: 0,
      },
    },
    series,
  };
}
