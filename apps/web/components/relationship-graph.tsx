import { useEffect, useMemo, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { AppLink } from "@/components/app-link";
import { ArrowRightIcon, NetworkIcon } from "@/components/icons";
import { apiRequest } from "@/lib/api";
import type {
  RelationshipGraph as RelationshipGraphData,
  RelationshipGraphEdge,
  RelationshipGraphNode,
} from "@/lib/types";

const VISIBLE_NODE_LIMIT = 16;
const COMPACT_NODE_LIMIT = 8;
const WIDTH = 1000;
const HEIGHT = 620;

type Point = { x: number; y: number; distance: number };

function graphIndex(data: RelationshipGraphData) {
  const nodes = new Map(data.nodes.map((node) => [node.id, node]));
  const adjacency = new Map<string, Set<string>>();
  for (const node of data.nodes) adjacency.set(node.id, new Set());
  for (const edge of data.edges) {
    adjacency.get(edge.source)?.add(edge.target);
    adjacency.get(edge.target)?.add(edge.source);
  }
  return { nodes, adjacency };
}

function distancesFrom(centerId: string, adjacency: Map<string, Set<string>>) {
  const distances = new Map([[centerId, 0]]);
  const parents = new Map<string, string>();
  const queue = [centerId];
  for (let index = 0; index < queue.length; index += 1) {
    const current = queue[index];
    for (const neighbor of adjacency.get(current) || []) {
      if (distances.has(neighbor)) continue;
      distances.set(neighbor, (distances.get(current) || 0) + 1);
      parents.set(neighbor, current);
      queue.push(neighbor);
    }
  }
  return { distances, parents };
}

function visibleNodes(
  data: RelationshipGraphData,
  centerId: string,
  adjacency: Map<string, Set<string>>,
  limit: number,
) {
  const { distances, parents } = distancesFrom(centerId, adjacency);
  const center = data.nodes.find((node) => node.id === centerId) || data.nodes[0];
  if (!center) return { nodes: [], distances, parents };
  const candidates = data.nodes
    .filter((node) => node.id !== center.id && distances.has(node.id))
    .sort((left, right) => {
      const distanceDelta = (distances.get(left.id) || 99) - (distances.get(right.id) || 99);
      if (distanceDelta) return distanceDelta;
      const setDelta = Number(right.type === "set") - Number(left.type === "set");
      if (setDelta) return setDelta;
      const weightDelta = right.weight - left.weight;
      if (weightDelta) return weightDelta;
      const degreeDelta = (adjacency.get(right.id)?.size || 0) - (adjacency.get(left.id)?.size || 0);
      return degreeDelta || left.label.localeCompare(right.label, "it");
    });
  let selectedCandidates = candidates;
  if (limit < VISIBLE_NODE_LIMIT) {
    const direct = candidates.filter((node) => distances.get(node.id) === 1).slice(0, 4);
    const sets = candidates.filter((node) => node.type === "set" && !direct.includes(node)).slice(0, 3);
    const prioritized = [...direct, ...sets];
    selectedCandidates = [
      ...prioritized,
      ...candidates.filter((node) => !prioritized.includes(node)),
    ];
  }
  const selected = [center, ...selectedCandidates.slice(0, limit - 1)];
  return { nodes: selected, distances, parents };
}

function useCompactGraph() {
  const [compact, setCompact] = useState(
    () => typeof window.matchMedia === "function" && window.matchMedia("(max-width: 740px)").matches,
  );
  useEffect(() => {
    if (typeof window.matchMedia !== "function") return;
    const media = window.matchMedia("(max-width: 740px)");
    const update = () => setCompact(media.matches);
    update();
    media.addEventListener("change", update);
    return () => media.removeEventListener("change", update);
  }, []);
  return compact;
}

function layout(nodes: RelationshipGraphNode[], distances: Map<string, number>) {
  const positions = new Map<string, Point>();
  if (!nodes.length) return positions;
  positions.set(nodes[0].id, { x: WIDTH / 2, y: HEIGHT / 2, distance: 0 });
  const rings = new Map<number, RelationshipGraphNode[]>();
  for (const node of nodes.slice(1)) {
    const distance = Math.min(distances.get(node.id) || 1, 2);
    rings.set(distance, [...(rings.get(distance) || []), node]);
  }
  for (const [distance, ring] of rings) {
    const radiusX = distance === 1 ? 220 : 390;
    const radiusY = distance === 1 ? 160 : 190;
    const existing = [...positions.values()].filter((point) => point.distance > 0);
    const offsets = distance === 1
      ? [-Math.PI / 2]
      : Array.from({ length: 24 }, (_, index) => -Math.PI / 2 + (Math.PI * 2 * index) / (24 * ring.length));
    const candidates = offsets.map((offset) => ring.map((_node, index) => {
      const angle = offset + (Math.PI * 2 * index) / ring.length;
      return {
        x: WIDTH / 2 + Math.cos(angle) * radiusX,
        y: HEIGHT / 2 + Math.sin(angle) * radiusY,
        distance,
      };
    }));
    const score = (points: Point[]) => {
      const comparisons = points.flatMap((point, index) => [
        ...existing.map((other) => [point, other]),
        ...points.slice(index + 1).map((other) => [point, other]),
      ]);
      return Math.min(...comparisons.map(([left, right]) => (
        ((left.x - right.x) / 175) ** 2 + ((left.y - right.y) / 78) ** 2
      )));
    };
    const points = candidates.reduce((best, candidate) => score(candidate) > score(best) ? candidate : best);
    ring.forEach((node, index) => {
      positions.set(node.id, points[index]);
    });
  }
  return positions;
}

function pathToCenter(targetId: string | null, centerId: string, parents: Map<string, string>) {
  const nodes = new Set([centerId]);
  const edges = new Set<string>();
  let current = targetId;
  while (current && current !== centerId) {
    nodes.add(current);
    const parent = parents.get(current);
    if (!parent) break;
    edges.add([current, parent].sort().join("|"));
    current = parent;
  }
  return { nodes, edges };
}

function edgeKey(edge: RelationshipGraphEdge) {
  return [edge.source, edge.target].sort().join("|");
}

export function RelationshipGraph() {
  const [data, setData] = useState<RelationshipGraphData | null>(null);
  const [centerId, setCenterId] = useState<string | null>(null);
  const [hoveredId, setHoveredId] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [error, setError] = useState("");
  const compact = useCompactGraph();

  useEffect(() => {
    let active = true;
    apiRequest<RelationshipGraphData>("/studio/relationship-graph")
      .then((result) => {
        if (!active) return;
        setData(result);
        setCenterId(result.center_id);
      })
      .catch((reason) => {
        if (active) setError(reason instanceof Error ? reason.message : "Non riesco ad aprire il grafo.");
      });
    return () => { active = false; };
  }, []);

  const index = useMemo(() => data ? graphIndex(data) : null, [data]);
  const view = useMemo(
    () => data && index && centerId
      ? visibleNodes(data, centerId, index.adjacency, compact ? COMPACT_NODE_LIMIT : VISIBLE_NODE_LIMIT)
      : { nodes: [], distances: new Map<string, number>(), parents: new Map<string, string>() },
    [centerId, compact, data, index],
  );
  const positions = useMemo(() => layout(view.nodes, view.distances), [view]);
  const visibleIds = useMemo(() => new Set(view.nodes.map((node) => node.id)), [view.nodes]);
  const visibleEdges = useMemo(
    () => data?.edges.filter((edge) => visibleIds.has(edge.source) && visibleIds.has(edge.target)) || [],
    [data, visibleIds],
  );
  const lineage = useMemo(
    () => pathToCenter(hoveredId, centerId || "", view.parents),
    [centerId, hoveredId, view.parents],
  );
  const center = centerId && index ? index.nodes.get(centerId) : null;
  const results = useMemo(() => {
    const needle = query.trim().toLocaleLowerCase("it-IT");
    if (!needle || !data) return [];
    return data.nodes
      .filter((node) => `${node.label} ${node.summary}`.toLocaleLowerCase("it-IT").includes(needle))
      .slice(0, 8);
  }, [data, query]);

  function recenter(nodeId: string) {
    setCenterId(nodeId);
    setHoveredId(null);
    setQuery("");
  }

  function anotherNode() {
    if (!data || !centerId) return;
    const candidates = data.nodes.filter((node) => node.type === "set" && node.member_count > 1);
    const fallback = data.nodes.filter((node) => node.type !== "professional");
    const sequence = candidates.length ? candidates : fallback;
    if (!sequence.length) return;
    const currentIndex = sequence.findIndex((node) => node.id === centerId);
    recenter(sequence[(currentIndex + 1) % sequence.length].id);
  }

  if (error) return <main className="graph-page"><div className="inline-error">{error}</div></main>;
  if (!data || !centerId) return <main className="graph-page"><div className="loading-line">Sto componendo il grafo…</div></main>;
  const hiddenCount = Math.max(0, data.nodes.length - view.nodes.length);

  return (
    <main className="graph-page">
      <header className="graph-header">
        <div>
          <p>Relazioni leggibili</p>
          <h1>Grafo</h1>
          <span>Conversazioni e insiemi emergenti, senza farti mantenere una pipeline.</span>
        </div>
        <div className="graph-header__profile">
          <span>Profilo dal backend</span>
          <strong>{data.profile.vertical_label || "Generico"}</strong>
        </div>
      </header>

      <div className="graph-toolbar">
        <label>
          <span>Cerca nel grafo</span>
          <input
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Persona, tema, situazione…"
          />
          <AnimatePresence>
            {query.trim() && (
              <motion.div className="graph-search-results" initial={{ opacity: 0, y: -4 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }}>
                {results.length ? results.map((node) => (
                  <button key={node.id} type="button" onClick={() => recenter(node.id)}>
                    <span>{node.type === "set" ? "Insieme" : node.type === "person" ? "Persona" : "Centro"}</span>
                    <strong>{node.label}</strong>
                  </button>
                )) : <p>Nessun nodo trovato.</p>}
              </motion.div>
            )}
          </AnimatePresence>
        </label>
        <button type="button" onClick={anotherNode}>Un altro nodo <ArrowRightIcon /></button>
      </div>

      <div className="graph-layout">
        <section className="graph-canvas" aria-label="Grafo delle relazioni">
          <svg viewBox={`0 0 ${WIDTH} ${HEIGHT}`} role="presentation">
            {visibleEdges.map((edge) => {
              const source = positions.get(edge.source);
              const target = positions.get(edge.target);
              if (!source || !target) return null;
              const active = lineage.edges.has(edgeKey(edge));
              return (
                <line
                  key={edge.id}
                  className={`${edge.relation === "member_of" ? "is-derived" : "is-primary"}${active ? " is-active" : ""}`}
                  x1={source.x} y1={source.y} x2={target.x} y2={target.y}
                />
              );
            })}
          </svg>
          {view.nodes.map((node) => {
            const point = positions.get(node.id);
            if (!point) return null;
            const active = node.id === centerId || lineage.nodes.has(node.id);
            return (
              <motion.button
                layout
                key={node.id}
                type="button"
                aria-pressed={node.id === centerId}
                className={`graph-node graph-node--${node.type}${active ? " is-active" : ""}`}
                style={{ left: `${(point.x / WIDTH) * 100}%`, top: `${(point.y / HEIGHT) * 100}%` }}
                onMouseEnter={() => setHoveredId(node.id)}
                onMouseLeave={() => setHoveredId(null)}
                onFocus={() => setHoveredId(node.id)}
                onBlur={() => setHoveredId(null)}
                onClick={() => recenter(node.id)}
                initial={{ opacity: 0, scale: .86 }}
                animate={{ opacity: 1, scale: 1 }}
              >
                <span>{node.type === "set" ? `${node.member_count} persone` : node.type === "person" ? "Conversazione" : `${node.member_count} persone`}</span>
                <strong>{node.label}</strong>
              </motion.button>
            );
          })}
          {!data.nodes.some((node) => node.type === "person") && (
            <div className="graph-empty">
              <NetworkIcon />
              <p>Il grafo si formerà dalle conversazioni del tuo spazio pubblico.</p>
            </div>
          )}
          <footer>
            <span>{view.nodes.length} nodi visibili{hiddenCount ? ` · ${hiddenCount} nel grafo` : ""}</span>
            <span>Linea continua: conversazione · tratteggiata: insieme derivato</span>
          </footer>
        </section>

        <aside className="graph-inspector">
          <p>{center?.type === "set" ? "Insieme derivato" : center?.type === "person" ? "Persona" : "Il tuo spazio"}</p>
          <h2>{center?.label}</h2>
          <span>{center?.summary}</span>
          {center?.type === "set" && <strong>{center.member_count} {center.member_count === 1 ? "persona collegata" : "persone collegate"}</strong>}
          {center?.conversation_id && (
            <AppLink href={`/studio/conversazioni/${encodeURIComponent(center.conversation_id)}`}>
              Apri la conversazione <ArrowRightIcon />
            </AppLink>
          )}
          <div>
            <p>Come leggerlo</p>
            <span>Gli insiemi sono interpretazioni del backend: servono a orientarti, non definiscono l’identità di una persona.</span>
          </div>
          <small>Se correggi o scarti la memoria di una conversazione, il grafo viene ricalcolato.</small>
        </aside>
      </div>
    </main>
  );
}
