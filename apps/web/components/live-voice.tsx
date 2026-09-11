import { useEffect, useRef, useState } from 'react';
import { MicIcon } from '@/components/icons';
import { apiRequest } from '@/lib/api';
import { LiveVoiceConnection } from '@/lib/live-voice';

interface Props {
  endpoint: () => Promise<string>;
  disabled?: boolean;
  suspended?: boolean;
  onActiveChange: (active: boolean) => void;
  onAvailabilityChange: (available: boolean) => void;
  onSaved: () => void;
}

export function LiveVoice(props: Props) {
  const [available, setAvailable] = useState(false);
  const [state, setState] = useState<'idle' | 'connecting' | 'live' | 'stopping'>('idle');
  const [muted, setMuted] = useState(false);
  const [working, setWorking] = useState(false);
  const [error, setError] = useState('');
  const [captions, setCaptions] = useState({ user: '', assistant: '' });
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
    setState('connecting'); setError(''); setMuted(false); setCaptions({ user: '', assistant: '' });
    latest.current.onActiveChange(true);
    const voice = new LiveVoiceConnection(event => {
      if (connection.current !== voice) return;
      if (event.type === 'ready') setState('live');
      if (event.type === 'error') setError(event.message);
      if (event.type === 'working') {
        setWorking(event.active);
        if (!event.active) latest.current.onSaved();
      }
      if (event.type === 'transcript') setCaptions(current => ({
        ...current, [event.speaker]: (current[event.speaker] + event.delta).slice(-20000),
      }));
      if (event.type === 'stopped') {
        connection.current = null;
        setState('idle'); setWorking(false);
        latest.current.onActiveChange(false);
        latest.current.onSaved();
      }
    });
    connection.current = voice;
    void voice.start(() => latest.current.endpoint());
  }

  if (!available) return null;
  const active = state !== 'idle';
  return <section className={`live-voice${active ? ' is-active' : ''}`} aria-label="Conversazione vocale con l’AI">
    <div className="live-voice__controls">
      {!active ? <button type="button" onClick={start} disabled={props.disabled || props.suspended}>
        <MicIcon /> Parla con l’assistente
      </button> : <>
        <span role="status">{state === 'connecting' ? 'Collego il microfono…' : state === 'stopping' ? 'Termino la voce…' : muted ? 'Microfono spento' : 'Ti ascolto, anche mentre parlo'}</span>
        {state === 'live' && <button type="button" aria-pressed={muted} onClick={() => {
          connection.current?.mute(!muted); setMuted(!muted);
        }}>{muted ? 'Riattiva microfono' : 'Spegni microfono'}</button>}
        <button type="button" disabled={state === 'stopping'} onClick={() => {
          setState('stopping'); connection.current?.stop();
        }}>Termina voce</button>
      </>}
    </div>
    <p className="live-voice__notice">Parli con un’AI. Durante la sessione il microfono resta aperto: le parole vengono inviate subito e trascritte nella conversazione. L’audio non viene conservato da LAGGENTE.</p>
    {working && <p role="status">L’assistente sta elaborando la tua richiesta. Puoi continuare a parlare.</p>}
    {(captions.user || captions.assistant) && <details className="live-voice__captions">
      <summary>Trascrizione vocale — può contenere errori</summary>
      <p><strong>Tu</strong><br />{captions.user}</p>
      <p><strong>Assistente AI</strong><br />{captions.assistant}</p>
      <small>Il testo generato può includere parole che non hai sentito per un’interruzione.</small>
    </details>}
    {error && <p role="alert">{error}</p>}
  </section>;
}
