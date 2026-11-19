import { useMemo } from "react";
import { EChart } from "../charts/EChart";

/** Small seeded generator so the illustration is the same on every load. */
function rng(seed: number) {
  let s = seed;
  return () => {
    s = (s * 1664525 + 1013904223) % 4294967296;
    return s / 4294967296;
  };
}
type P = [number, number, number];

/** Rotating 3D transaction network with one planted laundering ring (pink). Illustrative sample data only. */
export function NetworkScene({ height = 460 }: { height?: number }) {
  const option = useMemo(() => {
    const r = rng(7);
    const nodes: P[] = Array.from({ length: 70 }, () => {
      const u = r() * 2 - 1;
      const t = r() * Math.PI * 2;
      const rad = 18 + r() * 24;
      const q = Math.sqrt(1 - u * u);
      return [rad * q * Math.cos(t), rad * u, rad * q * Math.sin(t)];
    });
    // Neighbour links, drawn as one polyline: a depth-first walk that steps back after each branch.
    const adj: number[][] = nodes.map(() => []);
    nodes.forEach((a, i) => {
      nodes
        .map((b, j) => ({
          j,
          d: Math.hypot(a[0] - b[0], a[1] - b[1], a[2] - b[2]),
        }))
        .filter((x) => x.j !== i)
        .sort((x, y) => x.d - y.d)
        .slice(0, 2)
        .forEach((n) => {
          adj[i]!.push(n.j);
          adj[n.j]!.push(i);
        });
    });
    const seen = new Set<number>();
    const walk: P[] = [];
    const dfs = (i: number) => {
      seen.add(i);
      walk.push(nodes[i]!);
      for (const j of adj[i]!) {
        if (!seen.has(j)) {
          dfs(j);
          walk.push(nodes[i]!);
        }
      }
    };
    nodes.forEach((_, i) => {
      if (!seen.has(i)) dfs(i);
    });
    const ring: P[] = Array.from({ length: 5 }, (_, k) => {
      const a = (k / 5) * Math.PI * 2;
      return [Math.cos(a) * 16, Math.sin(a * 2) * 6 + 4, Math.sin(a) * 16];
    });
    const ringLoop: P[] = [...ring, ring[0]!];
    const hidden = { show: false, type: "value", min: -50, max: 50 };
    return {
      xAxis3D: hidden,
      yAxis3D: hidden,
      zAxis3D: hidden,
      grid3D: {
        show: false,
        boxWidth: 100,
        boxHeight: 100,
        boxDepth: 100,
        environment: "none",
        viewControl: {
          autoRotate: true,
          autoRotateSpeed: 10,
          distance: 100,
          alpha: 18,
          zoomSensitivity: 0,
          panSensitivity: 0,
        },
      },
      series: [
        {
          type: "line3D",
          coordinateSystem: "cartesian3D",
          data: walk,
          lineStyle: { width: 1, color: "#6366f1", opacity: 0.35 },
          silent: true,
        },
        {
          type: "scatter3D",
          coordinateSystem: "cartesian3D",
          data: nodes,
          symbolSize: 6,
          itemStyle: { color: "#a5b4fc", opacity: 0.95 },
          silent: true,
        },
        {
          type: "line3D",
          coordinateSystem: "cartesian3D",
          data: ringLoop,
          lineStyle: { width: 4, color: "#f472b6", opacity: 1 },
          silent: true,
        },
        {
          type: "scatter3D",
          coordinateSystem: "cartesian3D",
          data: ring,
          symbolSize: 14,
          itemStyle: { color: "#f472b6", opacity: 1 },
          silent: true,
        },
      ],
    };
  }, []);
  return (
    <EChart
      option={option}
      height={height}
      label="Illustrative 3D transaction network slowly rotating. A ring of five accounts passing money in a loop is highlighted in pink."
    />
  );
}
