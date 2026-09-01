import { useEffect, useState, type FormEvent } from "react";
import { apiRequest } from "@/lib/api";
import type { CalendarConnection, CalendarStatus } from "@/lib/types";

const weekdays = [
  [0, "Lun"], [1, "Mar"], [2, "Mer"], [3, "Gio"], [4, "Ven"], [5, "Sab"], [6, "Dom"],
] as const;

export function StudioCalendar() {
  const [status, setStatus] = useState<CalendarStatus | null>(null);
  const [draft, setDraft] = useState<CalendarConnection | null>(null);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function load() {
    try {
      const result = await apiRequest<CalendarStatus>("/studio/calendar");
      setStatus(result);
      setDraft(result.connection);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Non è stato possibile leggere il calendario.");
    }
  }

  useEffect(() => { void load(); }, []);

  async function connect() {
    setBusy(true);
    setError(null);
    try {
      const result = await apiRequest<{ authorization_url: string }>("/studio/calendar/oauth/start", { method: "POST" });
      window.location.assign(result.authorization_url);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Collegamento Google non riuscito.");
      setBusy(false);
    }
  }

  async function save(event: FormEvent) {
    event.preventDefault();
    if (!draft) return;
    setBusy(true);
    setError(null);
    setMessage(null);
    try {
      const updated = await apiRequest<CalendarConnection>("/studio/calendar", {
        method: "PATCH",
        body: JSON.stringify({
          booking_enabled: draft.booking_enabled,
          timezone: draft.timezone,
          work_days: draft.work_days,
          day_start: draft.day_start,
          day_end: draft.day_end,
          duration_minutes: draft.duration_minutes,
          slot_interval_minutes: draft.slot_interval_minutes,
          buffer_minutes: draft.buffer_minutes,
          minimum_notice_minutes: draft.minimum_notice_minutes,
          appointment_title: draft.appointment_title,
          location: draft.location || null,
        }),
      });
      setDraft(updated);
      setStatus((current) => current ? { ...current, connection: updated } : current);
      setMessage(updated.booking_enabled ? "Prenotazione pubblica attiva." : "Impostazioni salvate; prenotazione pubblica in pausa.");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Salvataggio non riuscito.");
    } finally {
      setBusy(false);
    }
  }

  async function disconnect() {
    if (!window.confirm("Scollegare Google Calendar da LAGGENTE? Gli appuntamenti già creati restano nel calendario.")) return;
    setBusy(true);
    try {
      await apiRequest("/studio/calendar", { method: "DELETE" });
      setStatus((current) => current ? { ...current, connection: null } : current);
      setDraft(null);
      setMessage("Google Calendar scollegato da LAGGENTE.");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Scollegamento non riuscito.");
    } finally {
      setBusy(false);
    }
  }

  function toggleDay(day: number) {
    if (!draft) return;
    const selected = draft.work_days.includes(day)
      ? draft.work_days.filter((item) => item !== day)
      : [...draft.work_days, day].sort();
    if (selected.length) setDraft({ ...draft, work_days: selected });
  }

  return (
    <main className="calendar-page">
      <header className="workspace-header">
        <div><p>Disponibilità verificata</p><h1>Google Calendar</h1></div>
        {draft && <span className="calendar-connection-state"><i /> {draft.provider_email}</span>}
      </header>
      <section className="calendar-intro">
        <p className="eyebrow">Appuntamenti senza agenda pubblica</p>
        <h2>L’assistente propone soltanto orari realmente liberi.</h2>
        <p>LAGGENTE legge esclusivamente occupato/libero e crea un evento quando la persona sceglie un orario preciso. Titoli e dettagli degli altri eventi non vengono mostrati.</p>
      </section>
      {error && <p className="calendar-feedback is-error" role="alert">{error}</p>}
      {message && <p className="calendar-feedback" role="status">{message}</p>}
      {status && !status.available && (
        <section className="calendar-empty"><h3>Integrazione non ancora attiva</h3><p>Le credenziali Google Calendar devono essere configurate sul server.</p></section>
      )}
      {status?.available && !draft && (
        <section className="calendar-empty">
          <h3>Collega il calendario professionale</h3>
          <p>Google mostrerà i permessi richiesti prima di condividere disponibilità e creazione eventi.</p>
          <button className="button button--ink" type="button" onClick={() => void connect()} disabled={busy}>{busy ? "Apro Google…" : "Collega Google Calendar"}</button>
        </section>
      )}
      {draft && (
        <form className="calendar-settings" onSubmit={save}>
          <label className="calendar-toggle">
            <input type="checkbox" checked={draft.booking_enabled} onChange={(event) => setDraft({ ...draft, booking_enabled: event.target.checked })} />
            <span><strong>Permetti all’assistente di fissare appuntamenti</strong><small>Puoi metterlo in pausa in qualsiasi momento.</small></span>
          </label>
          <div className="calendar-form-grid">
            <label><span>Nome appuntamento</span><input value={draft.appointment_title} onChange={(event) => setDraft({ ...draft, appointment_title: event.target.value })} required /></label>
            <label><span>Luogo o modalità</span><input value={draft.location || ""} onChange={(event) => setDraft({ ...draft, location: event.target.value })} placeholder="In agenzia oppure videochiamata" /></label>
            <label><span>Durata</span><select value={draft.duration_minutes} onChange={(event) => setDraft({ ...draft, duration_minutes: Number(event.target.value) as CalendarConnection["duration_minutes"] })}><option value="15">15 minuti</option><option value="30">30 minuti</option><option value="45">45 minuti</option><option value="60">60 minuti</option><option value="90">90 minuti</option></select></label>
            <label><span>Preavviso minimo</span><select value={draft.minimum_notice_minutes} onChange={(event) => setDraft({ ...draft, minimum_notice_minutes: Number(event.target.value) })}><option value="60">1 ora</option><option value="180">3 ore</option><option value="720">12 ore</option><option value="1440">1 giorno</option><option value="2880">2 giorni</option></select></label>
            <label><span>Dalle</span><input type="time" value={draft.day_start} onChange={(event) => setDraft({ ...draft, day_start: event.target.value })} required /></label>
            <label><span>Alle</span><input type="time" value={draft.day_end} onChange={(event) => setDraft({ ...draft, day_end: event.target.value })} required /></label>
            <label><span>Pausa fra appuntamenti</span><select value={draft.buffer_minutes} onChange={(event) => setDraft({ ...draft, buffer_minutes: Number(event.target.value) })}><option value="0">Nessuna</option><option value="15">15 minuti</option><option value="30">30 minuti</option><option value="60">60 minuti</option></select></label>
            <label><span>Fuso orario</span><input value={draft.timezone} onChange={(event) => setDraft({ ...draft, timezone: event.target.value })} required /></label>
          </div>
          <fieldset className="calendar-days"><legend>Giorni prenotabili</legend>{weekdays.map(([day, label]) => <button type="button" key={day} className={draft.work_days.includes(day) ? "is-selected" : ""} onClick={() => toggleDay(day)} aria-pressed={draft.work_days.includes(day)}>{label}</button>)}</fieldset>
          <div className="calendar-actions"><button className="button button--ink" type="submit" disabled={busy}>{busy ? "Salvo…" : "Salva impostazioni"}</button><button className="button button--ghost" type="button" onClick={() => void disconnect()} disabled={busy}>Scollega</button></div>
        </form>
      )}
    </main>
  );
}
