import { useCallback, useEffect, useState } from "react";
import { AppLink as Link } from "@/components/app-link";
import { ArrowUpRightIcon, CheckIcon, LayersIcon } from "@/components/icons";
import { RevisionInspector } from "@/components/revision-inspector";
import { InlineError, LoadingLine } from "@/components/status";
import { useStudioSession } from "@/components/studio-shell";
import { apiRequest, unwrapList } from "@/lib/api";
import { formatDateTime } from "@/lib/format";
import { publicSpaceHref } from "@/lib/hosts";
import { normalizeRevision } from "@/lib/revisions";
import type { ConfigRevision } from "@/lib/types";

export function SpaceRevisions() {
  const { session } = useStudioSession();
  const [revisions, setRevisions] = useState<ConfigRevision[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [listResult, spaceResult] = await Promise.all([
        apiRequest<unknown>("/studio/config/revisions"),
        apiRequest<unknown>("/studio/space"),
      ]);
      const values = unwrapList<unknown>(listResult, ["revisions", "items"])
        .map(normalizeRevision)
        .filter((item): item is ConfigRevision => Boolean(item));
      const space = spaceResult as Record<string, unknown>;
      const active = normalizeRevision(space.active_revision);
      const draft = normalizeRevision(space.latest_draft || space.proposed_revision);
      const unique = [...values];
      for (const item of [draft, active]) {
        if (item && !unique.some((existing) => existing.id === item.id)) unique.unshift(item);
      }
      unique.sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime());
      setRevisions(unique);
      setSelectedId((current) => current && unique.some((item) => item.id === current) ? current : (draft || active || unique[0])?.id || null);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Non è stato possibile leggere le versioni dello spazio.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { void load(); }, [load]);
  const selected = revisions.find((revision) => revision.id === selectedId) || null;
  const active = revisions.find((revision) => revision.status === "active") || null;

  return (
    <section className="space-page">
      <header className="page-header page-header--compact">
        <div><p>Spazio pubblico</p><h1>Ciò che le persone incontrano</h1><span>Solo la versione attiva guida l’assistente pubblico. Le bozze restano private finché non le confermi.</span></div>
        {session?.space?.is_active && session.space.slug_claimed && <Link className="button button--outline" href={publicSpaceHref(session.space.slug)} target="_blank">Apri lo spazio <ArrowUpRightIcon /></Link>}
      </header>
      {loading && <div className="space-page__loading"><LoadingLine label="Raccolgo le versioni…" /></div>}
      {error && <div className="space-page__loading"><InlineError message={error} retry={load} /></div>}
      {!loading && !error && !revisions.length && (
        <div className="space-empty"><LayersIcon /><h2>Lo spazio non ha ancora una versione.</h2><p>Parla con lo Studio: preparerà una prima proposta concreta da rivedere e attivare.</p><Link href="/studio">Torna alla conversazione</Link></div>
      )}
      {!!revisions.length && (
        <div className="space-revisions-layout">
          <aside className="revision-history">
            <header><p>Versioni</p><span>{revisions.length}</span></header>
            <div>
              {revisions.map((revision) => (
                <button type="button" key={revision.id} onClick={() => setSelectedId(revision.id)} className={revision.id === selectedId ? "is-selected" : ""}>
                  <i className={`revision-dot revision-dot--${revision.status}`} />
                  <span><strong>{revision.title}</strong><small>{formatDateTime(revision.created_at)}</small></span>
                  {revision.status === "active" && <em><CheckIcon /> attiva</em>}
                  {(revision.status === "draft" || revision.status === "proposed") && <em>bozza</em>}
                </button>
              ))}
            </div>
            <p className="revision-history__note">Attivare una versione non cambia il codice del sito. Cambia soltanto ciò che il tuo spazio esprime.</p>
          </aside>
          <RevisionInspector
            key={selected?.id}
            revision={selected}
            activeRevision={active}
            title="Versione selezionata"
            onActivated={(activated) => setRevisions((current) => current.map((revision) => revision.id === activated.id ? { ...activated, status: "active" } : revision.status === "active" ? { ...revision, status: "historical" } : revision))}
          />
        </div>
      )}
    </section>
  );
}
