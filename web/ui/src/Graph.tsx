import { useEffect, useRef } from "react";
import { Network } from "vis-network/standalone";
import type { GraphNode, GraphEdge } from "@/lib/api";

const COLORS: Record<string, string> = {
  username: "#4c8dff", url: "#3fb950", email: "#d29922", domain: "#a371f7",
  ip: "#f778ba", phone: "#56d4dd", person: "#ff7b72", company: "#e3b341",
};

export default function Graph({ nodes, edges, height = 420 }: { nodes: GraphNode[]; edges: GraphEdge[]; height?: number }) {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!ref.current) return;
    const visNodes = nodes.map((n) => ({
      id: n.id,
      label: n.value.length > 26 ? n.value.slice(0, 24) + "…" : n.value,
      title: `${n.type}: ${n.value}`,
      color: { background: COLORS[n.type] || "#6b7684", border: "transparent" },
      font: { color: "#e6edf3", size: 13 },
      shape: "dot",
      size: n.type === "username" || n.type === "person" ? 18 : 12,
    }));
    const visEdges = edges.map((e, i) => ({
      id: i, from: e.source, to: e.target, label: e.rel,
      font: { color: "#9aa7b5", size: 10, strokeWidth: 0 },
      color: { color: "#39414f" }, arrows: "to",
    }));
    const net = new Network(ref.current, { nodes: visNodes, edges: visEdges }, {
      physics: { stabilization: true, barnesHut: { springLength: 130 } },
      interaction: { hover: true, tooltipDelay: 120 },
    });
    return () => net.destroy();
  }, [nodes, edges]);

  return <div ref={ref} style={{ height, background: "var(--surface-1)", border: "1px solid var(--border)", borderRadius: 12 }} />;
}
