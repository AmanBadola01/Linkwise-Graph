"use client";

import {
  forceCenter,
  forceCollide,
  forceLink,
  forceManyBody,
  forceSimulation,
  type Simulation,
  type SimulationLinkDatum,
  type SimulationNodeDatum,
} from "d3-force";
import { useCallback, useEffect, useRef, useState, type ReactNode } from "react";
import type { GraphEdge, GraphNode } from "@/lib/graph-types";
import { colorForType, resolveNodeRef } from "@/lib/graph-layout";

type SimNode = GraphNode &
  SimulationNodeDatum & {
    r: number;
    labelLines: string[];
  };

type SimLink = SimulationLinkDatum<SimNode> & {
  id: string;
  type: string;
  lit: boolean;
};

type Props = {
  nodes: GraphNode[];
  edges: GraphEdge[];
  height?: number;
  highlightIds?: Set<string>;
  compact?: boolean;
};

/** Max zoom-in ~1.8× fit view; scroll and toolbar clamp here. */
const ZOOM_MIN = 0.3;
const ZOOM_MAX = 1.85;

function clampZoom(k: number): number {
  return Math.min(ZOOM_MAX, Math.max(ZOOM_MIN, k));
}

function labelLines(name: string, compact: boolean): { lines: string[]; r: number } {
  const maxLines = compact ? 2 : 2;
  const perLine = compact ? 11 : 14;
  const lines: string[] = [];
  const words = name.trim().split(/\s+/);
  let current = "";
  for (const w of words) {
    const next = current ? `${current} ${w}` : w;
    if (next.length <= perLine) {
      current = next;
    } else {
      if (current) lines.push(current);
      current = w.length > perLine ? `${w.slice(0, perLine - 1)}…` : w;
      if (lines.length >= maxLines) break;
    }
  }
  if (current && lines.length < maxLines) lines.push(current);
  if (lines.length === 0) lines.push(name.length > perLine ? `${name.slice(0, perLine - 1)}…` : name);

  const longest = Math.max(...lines.map((l) => l.length));
  const base = compact ? 24 : 30 + Math.min(12, (name.length > 0 ? 4 : 0));
  const r = Math.max(base, Math.min(compact ? 40 : 58, 16 + longest * 3.4 + lines.length * 6));
  return { lines, r };
}

type EdgeGeom = {
  x1: number;
  y1: number;
  x2: number;
  y2: number;
  ux: number;
  uy: number;
  label: string;
  lit: boolean;
  link: SimLink;
};

export default function Neo4jGraphView({ nodes, edges, height = 560, highlightIds, compact = false }: Props) {
  const wrapRef = useRef<HTMLDivElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const simRef = useRef<Simulation<SimNode, SimLink> | null>(null);
  const nodesRef = useRef<SimNode[]>([]);
  const linksRef = useRef<SimLink[]>([]);
  const transformRef = useRef({ x: 0, y: 0, k: 1 });
  const dragRef = useRef<{ kind: "pan" | "node"; nodeId?: string; ox: number; oy: number } | null>(null);
  const [selected, setSelected] = useState<GraphNode | null>(null);
  const [, bump] = useState(0);

  const draw = useCallback(() => {
    const canvas = canvasRef.current;
    const wrap = wrapRef.current;
    if (!canvas || !wrap) return;

    const dpr = Math.min(window.devicePixelRatio, 2);
    const w = wrap.clientWidth;
    const h = height;
    canvas.width = w * dpr;
    canvas.height = h * dpr;
    canvas.style.width = `${w}px`;
    canvas.style.height = `${h}px`;

    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.fillStyle = compact ? "#1a334d" : "#23272e";
    ctx.fillRect(0, 0, w, h);

    const { x: tx, y: ty, k } = transformRef.current;
    ctx.save();
    ctx.translate(tx, ty);
    ctx.scale(k, k);

    const simNodes = nodesRef.current;
    const simLinks = linksRef.current;

    const edgeGeoms: EdgeGeom[] = [];

    for (const link of simLinks) {
      const s = link.source as SimNode;
      const t = link.target as SimNode;
      const dx = t.x! - s.x!;
      const dy = t.y! - s.y!;
      const dist = Math.hypot(dx, dy) || 1;
      const ux = dx / dist;
      const uy = dy / dist;
      const x1 = s.x! + ux * (s.r + 2);
      const y1 = s.y! + uy * (s.r + 2);
      const x2 = t.x! - ux * (t.r + 8);
      const y2 = t.y! - uy * (t.r + 8);

      ctx.strokeStyle = link.lit ? "rgba(220, 228, 236, 0.7)" : "rgba(180, 190, 200, 0.3)";
      ctx.lineWidth = link.lit ? 1.4 : 1;
      ctx.beginPath();
      ctx.moveTo(x1, y1);
      ctx.lineTo(x2, y2);
      ctx.stroke();

      const ax = x2;
      const ay = y2;
      const size = 7;
      ctx.beginPath();
      ctx.moveTo(ax, ay);
      ctx.lineTo(ax - ux * size - uy * size * 0.45, ay - uy * size + ux * size * 0.45);
      ctx.lineTo(ax - ux * size + uy * size * 0.45, ay - uy * size - ux * size * 0.45);
      ctx.closePath();
      ctx.fillStyle = link.lit ? "rgba(220, 228, 236, 0.85)" : "rgba(180, 190, 200, 0.45)";
      ctx.fill();

      edgeGeoms.push({
        x1,
        y1,
        x2,
        y2,
        ux,
        uy,
        label: link.type.replace(/_/g, " ").toUpperCase(),
        lit: link.lit,
        link,
      });
    }

    for (const n of simNodes) {
      const lit = !highlightIds || highlightIds.has(n.id);
      const fill = colorForType(n.type);
      ctx.globalAlpha = lit ? 1 : 0.38;
      ctx.beginPath();
      ctx.arc(n.x!, n.y!, n.r, 0, Math.PI * 2);
      ctx.fillStyle = fill;
      ctx.fill();
      ctx.strokeStyle = selected?.id === n.id ? "#ffffff" : lit ? "rgba(255,255,255,0.35)" : "rgba(255,255,255,0.12)";
      ctx.lineWidth = selected?.id === n.id ? 2.5 : 1.2;
      ctx.stroke();

      ctx.font = `600 ${compact ? 8 : 10}px var(--jakarta, sans-serif)`;
      ctx.textAlign = "center";
      ctx.textBaseline = "middle";
      const lineH = compact ? 10 : 12;
      const startY = n.y! - ((n.labelLines.length - 1) * lineH) / 2;
      n.labelLines.forEach((line, i) => {
        const ly = startY + i * lineH;
        ctx.lineWidth = 3;
        ctx.strokeStyle = "rgba(232, 165, 152, 0.95)";
        ctx.strokeText(line, n.x!, ly);
        ctx.fillStyle = "#1a2433";
        ctx.fillText(line, n.x!, ly);
      });
      ctx.globalAlpha = 1;
    }

  if (!compact) {
      const insideNode = (x: number, y: number, margin = 4) =>
        simNodes.some((n) => Math.hypot(n.x! - x, n.y! - y) < n.r + margin);

      for (const eg of edgeGeoms) {
        const dist = Math.hypot(eg.x2 - eg.x1, eg.y2 - eg.y1);
        if (dist < 36) continue;

        const normal = 16;
        for (const sign of [1, -1]) {
          const mx = (eg.x1 + eg.x2) / 2 + -eg.uy * normal * sign;
          const my = (eg.y1 + eg.y2) / 2 + eg.ux * normal * sign;
          if (!insideNode(mx, my, 2)) {
            ctx.font = "700 9px var(--jakarta, sans-serif)";
            const tw = ctx.measureText(eg.label).width;
            const padX = 6;
            const padY = 5;
            ctx.fillStyle = "rgba(30, 33, 38, 0.96)";
            ctx.strokeStyle = "rgba(255,255,255,0.18)";
            ctx.lineWidth = 1;
            roundRect(ctx, mx - tw / 2 - padX, my - padY - 1, tw + padX * 2, padY * 2 + 2, 4);
            ctx.fill();
            ctx.stroke();
            ctx.fillStyle = eg.lit ? "#eef2f7" : "#a8b1bb";
            ctx.textAlign = "center";
            ctx.textBaseline = "middle";
            ctx.fillText(eg.label, mx, my);
            break;
          }
        }
      }
    }

    ctx.restore();
  }, [compact, height, highlightIds, selected?.id]);

  useEffect(() => {
    const wrap = wrapRef.current;
    if (!wrap || nodes.length === 0) return;

    const byId = new Map(nodes.map((n) => [n.id, n]));
    const byName = new Map(nodes.map((n) => [n.name, n]));

    const simNodes: SimNode[] = nodes.map((n) => {
      const { lines, r } = labelLines(n.name, compact);
      return {
        ...n,
        r,
        labelLines: lines,
        x: (Math.random() - 0.5) * 60,
        y: (Math.random() - 0.5) * 60,
      };
    });

    const idSet = new Set(simNodes.map((n) => n.id));
    const simLinks: SimLink[] = [];
    for (const e of edges) {
      const sId = resolveNodeRef(e.source, byId, byName);
      const tId = resolveNodeRef(e.target, byId, byName);
      if (!sId || !tId || !idSet.has(sId) || !idSet.has(tId)) continue;
      const lit = !highlightIds || (highlightIds.has(sId) && highlightIds.has(tId));
      simLinks.push({ id: e.id, type: e.type, source: sId, target: tId, lit });
    }

    nodesRef.current = simNodes;
    linksRef.current = simLinks;

    simRef.current?.stop();
    const sim = forceSimulation(simNodes)
      .force(
        "link",
        forceLink<SimNode, SimLink>(simLinks)
          .id((d) => d.id)
          .distance((l) => {
            const s = l.source as SimNode;
            const t = l.target as SimNode;
            return s.r + t.r + (compact ? 100 : 130);
          })
          .strength(0.72),
      )
      .force("charge", forceManyBody().strength(compact ? -320 : -520).distanceMax(420))
      .force("center", forceCenter(0, 0).strength(0.05))
      .force(
        "collide",
        forceCollide<SimNode>()
          .radius((d) => d.r + (compact ? 14 : 22))
          .strength(1)
          .iterations(2),
      )
      .alpha(1)
      .on("tick", () => {
        draw();
      });

    simRef.current = sim;

    const center = () => {
      if (!wrap || simNodes.length === 0) return;
      let minX = Infinity,
        maxX = -Infinity,
        minY = Infinity,
        maxY = -Infinity;
      for (const n of simNodes) {
        minX = Math.min(minX, n.x!);
        maxX = Math.max(maxX, n.x!);
        minY = Math.min(minY, n.y!);
        maxY = Math.max(maxY, n.y!);
      }
      const gw = maxX - minX + 120;
      const gh = maxY - minY + 120;
      const k = Math.min(wrap.clientWidth / gw, height / gh, 1.8) * 0.92;
      transformRef.current = {
        x: wrap.clientWidth / 2 - ((minX + maxX) / 2) * k,
        y: height / 2 - ((minY + maxY) / 2) * k,
        k,
      };
      draw();
    };

    const endTimer = window.setTimeout(center, 900);

    const ro = new ResizeObserver(() => draw());
    ro.observe(wrap);

    return () => {
      window.clearTimeout(endTimer);
      ro.disconnect();
      sim.stop();
    };
  }, [nodes, edges, compact, height, highlightIds, draw]);

  const screenToWorld = (sx: number, sy: number) => {
    const { x, y, k } = transformRef.current;
    return { x: (sx - x) / k, y: (sy - y) / k };
  };

  const pickNode = (sx: number, sy: number): SimNode | null => {
    const { x, y } = screenToWorld(sx, sy);
    let found: SimNode | null = null;
    for (const n of nodesRef.current) {
      if (Math.hypot(n.x! - x, n.y! - y) <= n.r + 4) found = n;
    }
    return found;
  };

  const onPointerDown = (e: React.PointerEvent) => {
    const rect = canvasRef.current?.getBoundingClientRect();
    if (!rect) return;
    const sx = e.clientX - rect.left;
    const sy = e.clientY - rect.top;
    const hit = pickNode(sx, sy);
    (e.target as HTMLCanvasElement).setPointerCapture(e.pointerId);
    if (hit) {
      hit.fx = hit.x;
      hit.fy = hit.y;
      dragRef.current = { kind: "node", nodeId: hit.id, ox: sx, oy: sy };
      setSelected(hit);
      simRef.current?.alphaTarget(0.25).restart();
    } else {
      dragRef.current = { kind: "pan", ox: sx - transformRef.current.x, oy: sy - transformRef.current.y };
      setSelected(null);
    }
  };

  const onPointerMove = (e: React.PointerEvent) => {
    const drag = dragRef.current;
    const rect = canvasRef.current?.getBoundingClientRect();
    if (!drag || !rect) return;
    const sx = e.clientX - rect.left;
    const sy = e.clientY - rect.top;
    if (drag.kind === "pan") {
      transformRef.current.x = sx - drag.ox;
      transformRef.current.y = sy - drag.oy;
      draw();
      return;
    }
    const { x, y } = screenToWorld(sx, sy);
    const n = nodesRef.current.find((nd) => nd.id === drag.nodeId);
    if (n) {
      n.fx = x;
      n.fy = y;
    }
  };

  const onPointerUp = (e: React.PointerEvent) => {
    const drag = dragRef.current;
    if (drag?.kind === "node") {
      const n = nodesRef.current.find((nd) => nd.id === drag.nodeId);
      if (n) {
        n.fx = null;
        n.fy = null;
      }
      simRef.current?.alphaTarget(0);
    }
    dragRef.current = null;
    try {
      (e.target as HTMLCanvasElement).releasePointerCapture(e.pointerId);
    } catch {
      /* ignore */
    }
  };

  const onWheel = (e: React.WheelEvent) => {
    e.preventDefault();
    const rect = canvasRef.current?.getBoundingClientRect();
    if (!rect) return;
    const sx = e.clientX - rect.left;
    const sy = e.clientY - rect.top;
    const factor = e.deltaY > 0 ? 0.92 : 1.08;
    const t = transformRef.current;
    const wx = (sx - t.x) / t.k;
    const wy = (sy - t.y) / t.k;
    const nk = clampZoom(t.k * factor);
    transformRef.current = { x: sx - wx * nk, y: sy - wy * nk, k: nk };
    draw();
  };

  const zoomBy = (factor: number) => {
    const wrap = wrapRef.current;
    if (!wrap) return;
    const cx = wrap.clientWidth / 2;
    const cy = height / 2;
    const t = transformRef.current;
    const wx = (cx - t.x) / t.k;
    const wy = (cy - t.y) / t.k;
    const nk = clampZoom(t.k * factor);
    transformRef.current = { x: cx - wx * nk, y: cy - wy * nk, k: nk };
    draw();
    bump((n) => n + 1);
  };

  const fitView = () => {
    const wrap = wrapRef.current;
    const simNodes = nodesRef.current;
    if (!wrap || !simNodes.length) return;
    let minX = Infinity,
      maxX = -Infinity,
      minY = Infinity,
      maxY = -Infinity;
    for (const n of simNodes) {
      minX = Math.min(minX, n.x! - n.r);
      maxX = Math.max(maxX, n.x! + n.r);
      minY = Math.min(minY, n.y! - n.r);
      maxY = Math.max(maxY, n.y! + n.r);
    }
    const gw = maxX - minX + 80;
    const gh = maxY - minY + 80;
    const k = Math.min(wrap.clientWidth / gw, height / gh, 1.8) * 0.95;
    transformRef.current = {
      x: wrap.clientWidth / 2 - ((minX + maxX) / 2) * k,
      y: height / 2 - ((minY + maxY) / 2) * k,
      k,
    };
    draw();
  };

  if (nodes.length === 0) {
    return (
      <div
        className="flex items-center justify-center rounded-2xl border border-[#E8A598]/25 bg-[#23272e] text-sm text-[#F0DCC8]"
        style={{ height }}
      >
        No graph nodes to display.
      </div>
    );
  }

  const relatedEdges = selected
    ? edges.filter(
        (e) =>
          e.source === selected.name ||
          e.target === selected.name ||
          e.source === selected.id ||
          e.target === selected.id,
      )
    : [];

  // Keyboard support: focus the canvas, arrows pan, +/- zoom, 0 fits
  // (BUG-19 — previously mouse/touch only). A text alternative follows.
  const onCanvasKeyDown = (e: React.KeyboardEvent) => {
    const step = 40;
    const t = transformRef.current;
    if (e.key === "ArrowLeft") t.x += step;
    else if (e.key === "ArrowRight") t.x -= step;
    else if (e.key === "ArrowUp") t.y += step;
    else if (e.key === "ArrowDown") t.y -= step;
    else if (e.key === "+" || e.key === "=") return zoomBy(1.15);
    else if (e.key === "-") return zoomBy(0.87);
    else if (e.key === "0") return fitView();
    else return;
    e.preventDefault();
    draw();
  };

  return (
    <div className="space-y-3">
      {!compact && (
        <p className="text-xs text-[#F0DCC8]">
          Drag nodes · Drag background to pan · Scroll to zoom · Focus the graph and use arrow keys to pan, +/− to
          zoom, 0 to fit · Relationship labels on edges (Neo4j-style)
        </p>
      )}
      <div ref={wrapRef} className="relative w-full overflow-hidden rounded-2xl border border-[#E8A598]/20">
        <canvas
          ref={canvasRef}
          className="block w-full touch-none focus:outline focus:outline-2 focus:outline-[#E8A598]"
          style={{ height }}
          tabIndex={0}
          role="application"
          aria-label={`Knowledge graph with ${nodes.length} entities and ${edges.length} relationships. Use arrow keys to pan, plus and minus to zoom, zero to fit.`}
          onKeyDown={onCanvasKeyDown}
          onPointerDown={onPointerDown}
          onPointerMove={onPointerMove}
          onPointerUp={onPointerUp}
          onPointerLeave={onPointerUp}
          onWheel={onWheel}
        />
        {!compact && (
          <div className="absolute bottom-3 right-3 flex gap-1 rounded-lg border border-[#E8A598]/25 bg-[#1e2126]/90 p-1 shadow-lg">
            <ToolbarBtn title="Zoom in" onClick={() => zoomBy(1.15)}>
              +
            </ToolbarBtn>
            <ToolbarBtn title="Zoom out" onClick={() => zoomBy(0.87)}>
              −
            </ToolbarBtn>
            <ToolbarBtn title="Fit to screen" onClick={fitView}>
              ⤢
            </ToolbarBtn>
          </div>
        )}
      </div>
      {/* Text alternative for screen readers / keyboard users (BUG-19):
          the canvas itself is pixels only. */}
      <div className="sr-only" role="list" aria-label="Graph entities and relationships as text">
        {nodes.map((n) => (
          <p key={n.id} role="listitem">
            {n.name} ({n.type}){n.page ? `, page ${n.page}` : ""}
          </p>
        ))}
        {edges.map((e) => (
          <p key={e.id} role="listitem">
            {e.source} {e.type} {e.target}
          </p>
        ))}
      </div>
      {selected && !compact && (
        <div className="rounded-2xl border border-[#E8A598]/30 bg-[#0B132B]/15 p-4 text-sm text-[#EDE6DE]">
          <p className="text-xs uppercase tracking-wider text-[#F0DCC8]">Selected entity</p>
          <p className="mt-1 text-lg font-semibold text-white">{selected.name}</p>
          <ul className="mt-2 space-y-1 text-xs">
            <li>
              <span className="text-[#F0DCC8]">Type:</span> {selected.type}
            </li>
            {selected.degree != null && (
              <li>
                <span className="text-[#F0DCC8]">Connections:</span> {selected.degree}
              </li>
            )}
            {selected.page ? (
              <li>
                <span className="text-[#F0DCC8]">Page:</span> {selected.page}
              </li>
            ) : null}
          </ul>
          {selected.description ? (
            <p className="mt-3 text-xs leading-5 text-[#D9D0C8]">{selected.description}</p>
          ) : null}
          {relatedEdges.length > 0 && (
            <ul className="mt-3 space-y-1 text-xs text-[#F0DCC8]">
              {relatedEdges.slice(0, 8).map((e) => (
                <li key={e.id}>
                  {e.source} → <span className="text-white/90">{e.type}</span> → {e.target}
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  );
}

function roundRect(
  ctx: CanvasRenderingContext2D,
  x: number,
  y: number,
  w: number,
  h: number,
  r: number,
) {
  ctx.beginPath();
  ctx.moveTo(x + r, y);
  ctx.lineTo(x + w - r, y);
  ctx.quadraticCurveTo(x + w, y, x + w, y + r);
  ctx.lineTo(x + w, y + h - r);
  ctx.quadraticCurveTo(x + w, y + h, x + w - r, y + h);
  ctx.lineTo(x + r, y + h);
  ctx.quadraticCurveTo(x, y + h, x, y + h - r);
  ctx.lineTo(x, y + r);
  ctx.quadraticCurveTo(x, y, x + r, y);
  ctx.closePath();
}

function ToolbarBtn({
  children,
  title,
  onClick,
}: {
  children: ReactNode;
  title: string;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      title={title}
      onClick={onClick}
      className="flex h-8 w-8 items-center justify-center rounded-md text-sm text-white hover:bg-white/15"
    >
      {children}
    </button>
  );
}