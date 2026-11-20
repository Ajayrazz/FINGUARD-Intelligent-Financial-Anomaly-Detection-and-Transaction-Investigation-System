import { useEffect, useRef } from "react";

interface Node {
  x: number;
  y: number;
  vx: number;
  vy: number;
  px: number; // push velocity from the pointer / clicks (decays)
  py: number;
  r: number;
  hue: number;
}
interface Ripple {
  x: number;
  y: number;
  r: number;
  a: number;
}

/**
 * Animated network drawn behind the app. It reacts to the pointer:
 *  - nodes near the cursor are gently pushed away and the cursor "threads" to the closest nodes with glowing lines,
 *  - a click or tap sends out a ripple and a shockwave that scatters nearby nodes.
 * Purely visual: aria-hidden, never takes pointer events, pauses when the tab is hidden, and is drawn once (static,
 * no interaction) when the user prefers reduced motion.
 */
export function NetworkBackground() {
  const ref = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = ref.current;
    const ctx = canvas?.getContext?.("2d") ?? null;
    if (!canvas || !ctx) return; // e.g. jsdom
    const reduce =
      window.matchMedia?.("(prefers-reduced-motion: reduce)").matches ?? false;
    let w = 0;
    let h = 0;
    let nodes: Node[] = [];
    const ripples: Ripple[] = [];
    let raf = 0;
    const mouse = { x: -9999, y: -9999, on: false };
    const LINK = 150;
    const REACH = 190; // cursor thread distance
    const PUSH = 130; // cursor repel distance

    const resize = () => {
      const dpr = Math.min(window.devicePixelRatio || 1, 2);
      w = window.innerWidth;
      h = window.innerHeight;
      canvas.width = w * dpr;
      canvas.height = h * dpr;
      canvas.style.width = `${w}px`;
      canvas.style.height = `${h}px`;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      const count = Math.min(80, Math.round((w * h) / 18000));
      nodes = Array.from({ length: count }, () => ({
        x: Math.random() * w,
        y: Math.random() * h,
        vx: (Math.random() - 0.5) * 0.25,
        vy: (Math.random() - 0.5) * 0.25,
        px: 0,
        py: 0,
        r: 1 + Math.random() * 1.8,
        hue: 235 + Math.random() * 60, // indigo -> violet
      }));
    };

    const draw = () => {
      ctx.clearRect(0, 0, w, h);
      // soft glow under the cursor
      if (mouse.on) {
        const g = ctx.createRadialGradient(
          mouse.x,
          mouse.y,
          0,
          mouse.x,
          mouse.y,
          140,
        );
        g.addColorStop(0, "rgba(129,140,248,0.22)");
        g.addColorStop(1, "rgba(129,140,248,0)");
        ctx.fillStyle = g;
        ctx.fillRect(mouse.x - 140, mouse.y - 140, 280, 280);
      }
      for (let i = 0; i < nodes.length; i++) {
        const a = nodes[i]!;
        for (let j = i + 1; j < nodes.length; j++) {
          const b = nodes[j]!;
          const d = Math.hypot(a.x - b.x, a.y - b.y);
          if (d < LINK) {
            ctx.strokeStyle = `hsla(245, 80%, 70%, ${(1 - d / LINK) * 0.28})`;
            ctx.lineWidth = 1;
            ctx.beginPath();
            ctx.moveTo(a.x, a.y);
            ctx.lineTo(b.x, b.y);
            ctx.stroke();
          }
        }
      }
      // threads from the cursor to nearby nodes
      if (mouse.on) {
        for (const n of nodes) {
          const d = Math.hypot(n.x - mouse.x, n.y - mouse.y);
          if (d < REACH) {
            ctx.strokeStyle = `hsla(185, 95%, 70%, ${(1 - d / REACH) * 0.75})`;
            ctx.lineWidth = 1.4;
            ctx.beginPath();
            ctx.moveTo(mouse.x, mouse.y);
            ctx.lineTo(n.x, n.y);
            ctx.stroke();
          }
        }
      }
      for (const n of nodes) {
        const near =
          mouse.on && Math.hypot(n.x - mouse.x, n.y - mouse.y) < REACH;
        ctx.fillStyle = near
          ? "hsla(185, 95%, 78%, 0.95)"
          : `hsla(${n.hue}, 90%, 75%, 0.85)`;
        ctx.shadowColor = near
          ? "hsla(185, 95%, 65%, 1)"
          : `hsla(${n.hue}, 90%, 65%, 0.9)`;
        ctx.shadowBlur = near ? 14 : 8;
        ctx.beginPath();
        ctx.arc(n.x, n.y, near ? n.r + 0.8 : n.r, 0, Math.PI * 2);
        ctx.fill();
      }
      ctx.shadowBlur = 0;
      for (const r of ripples) {
        ctx.strokeStyle = `rgba(165,180,252,${r.a})`;
        ctx.lineWidth = 2;
        ctx.beginPath();
        ctx.arc(r.x, r.y, r.r, 0, Math.PI * 2);
        ctx.stroke();
      }
    };

    const step = () => {
      for (const n of nodes) {
        if (mouse.on) {
          const dx = n.x - mouse.x;
          const dy = n.y - mouse.y;
          const d = Math.hypot(dx, dy) || 1;
          if (d < PUSH) {
            const f = (1 - d / PUSH) * 0.9;
            n.px += (dx / d) * f;
            n.py += (dy / d) * f;
          }
        }
        n.x += n.vx + n.px;
        n.y += n.vy + n.py;
        n.px *= 0.93;
        n.py *= 0.93;
        if (n.x < -20) n.x = w + 20;
        if (n.x > w + 20) n.x = -20;
        if (n.y < -20) n.y = h + 20;
        if (n.y > h + 20) n.y = -20;
      }
      for (let i = ripples.length - 1; i >= 0; i--) {
        const r = ripples[i]!;
        r.r += 5;
        r.a -= 0.018;
        if (r.a <= 0) ripples.splice(i, 1);
      }
      draw();
      raf = requestAnimationFrame(step);
    };

    const onMove = (e: PointerEvent) => {
      mouse.x = e.clientX;
      mouse.y = e.clientY;
      mouse.on = true;
    };
    const onLeave = () => {
      mouse.on = false;
    };
    const onDown = (e: PointerEvent) => {
      ripples.push({ x: e.clientX, y: e.clientY, r: 8, a: 0.9 });
      for (const n of nodes) {
        const dx = n.x - e.clientX;
        const dy = n.y - e.clientY;
        const d = Math.hypot(dx, dy) || 1;
        if (d < 280) {
          const f = (1 - d / 280) * 7;
          n.px += (dx / d) * f;
          n.py += (dy / d) * f;
        }
      }
    };
    const onVisibility = () => {
      cancelAnimationFrame(raf);
      if (!document.hidden && !reduce) raf = requestAnimationFrame(step);
    };

    resize();
    draw();
    window.addEventListener("resize", resize);
    if (!reduce) {
      raf = requestAnimationFrame(step);
      window.addEventListener("pointermove", onMove, { passive: true });
      window.addEventListener("pointerdown", onDown, { passive: true });
      document.documentElement.addEventListener("pointerleave", onLeave);
      document.addEventListener("visibilitychange", onVisibility);
    }
    return () => {
      cancelAnimationFrame(raf);
      window.removeEventListener("resize", resize);
      window.removeEventListener("pointermove", onMove);
      window.removeEventListener("pointerdown", onDown);
      document.documentElement.removeEventListener("pointerleave", onLeave);
      document.removeEventListener("visibilitychange", onVisibility);
    };
  }, []);

  return (
    <canvas
      ref={ref}
      aria-hidden="true"
      className="pointer-events-none fixed inset-0 z-0"
    />
  );
}
