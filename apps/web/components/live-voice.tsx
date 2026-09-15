import { useEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { MicIcon } from '@/components/icons';
import { apiRequest } from '@/lib/api';
import { LiveVoiceConnection, type VoiceEvent } from '@/lib/live-voice';

interface Props {
  endpoint: () => Promise<string>;
  disabled?: boolean;
  suspended?: boolean;
  onActiveChange: (active: boolean) => void;
  onAvailabilityChange: (available: boolean) => void;
  onSaved: () => void;
  onTranscript?: (event: Extract<VoiceEvent, {type: 'transcript'}>) => void;
}

export function LiveVoice(props: Props) {
  const [available, setAvailable] = useState(false);
  const [state, setState] = useState<'idle' | 'connecting' | 'live' | 'stopping'>('idle');
  const [working, setWorking] = useState(false);
  const [error, setError] = useState('');
  const [playing, setPlaying] = useState(false);
  const [level, setLevel] = useState(0);
  const dialog = useRef<HTMLDialogElement>(null);
  const connection = useRef<LiveVoiceConnection | null>(null);
  const latest = useRef(props);
  useEffect(() => { latest.current = props; });
  useEffect(() => {
    let mounted = true;
    const stopOnLeave = () => connection.current?.stop();
    window.addEventListener("pagehide", stopOnLeave);
    void apiRequest<{ enabled: boolean }>('/voice/capabilities').then(({ enabled }) => {
      if (mounted) { setAvailable(enabled); latest.current.onAvailabilityChange(enabled); }
    }).catch(() => undefined);
    return () => {
      mounted = false;
      window.removeEventListener("pagehide", stopOnLeave);
      const voice = connection.current;
      connection.current = null;
      voice?.close();
    };
  }, []);
  useEffect(() => {
    if (props.suspended) connection.current?.stop();
  }, [props.suspended]);

  function start() {
    if (connection.current || props.disabled || props.suspended) return;
    setState('connecting'); setError(''); setLevel(0); setPlaying(false);
    latest.current.onActiveChange(true);
    const voice = new LiveVoiceConnection(event => {
      if (connection.current !== voice) return;
      if (event.type === 'ready') setState('live');
      if (event.type === 'error') setError(event.message);
      if (event.type === 'working') {
        setWorking(event.active);
        if (!event.active) latest.current.onSaved();
      }
      if (event.type === 'transcript') latest.current.onTranscript?.(event);
      if (event.type === 'level') setLevel(event.value);
      if (event.type === 'playback') setPlaying(event.active);
      if (event.type === 'stopped') {
        connection.current = null;
        setState('idle'); setWorking(false); setPlaying(false);
        latest.current.onActiveChange(false);
        latest.current.onSaved();
      }
    });
    connection.current = voice;
    void voice.start(() => latest.current.endpoint());
  }

  const active = state !== 'idle';
  useEffect(() => {
    if (active) dialog.current?.showModal();
  }, [active]);
  function stop() {
    setState('stopping'); connection.current?.stop();
  }
  if (!available) return null;
  return <section className="live-voice" aria-label="Conversazione vocale con l’AI">
    <div className="live-voice__controls">
      <button type="button" onClick={start} disabled={active || props.disabled || props.suspended}>
        <MicIcon /> Parla con l’assistente
      </button>
    </div>
    {active && createPortal(<dialog ref={dialog} className="voice-session" aria-label="Conversazione vocale con l’AI" onCancel={event => { event.preventDefault(); stop(); }}>
      <p className="voice-session__identity">LAGGENTE · Voce AI</p>
      <div className="voice-session__center">
        <div className="voice-session__orb" aria-hidden="true" style={{ transform: `scale(${1 + level * .55})`, borderRadius: `${50 - level * 10}% ${50 + level * 10}% 50% 50%`, opacity: .65 + level * .35 }} />
        <p role="status">{state === 'connecting' ? 'Mi collego…' : state === 'stopping' ? 'Termino la voce…' : playing ? 'Sto parlando' : working ? 'Ci sto lavorando…' : 'Ti ascolto'}</p>
      </div>
      <button className="voice-session__end" type="button" autoFocus disabled={state === 'stopping'} onClick={stop}>Termina voce</button>
    </dialog>, document.body)}
    {error && <p role="alert">{error}</p>}
  </section>;
}
