import { useEffect, useRef, useState } from 'react';
import { MicIcon } from '@/components/icons';
import { apiRequest } from '@/lib/api';
import { LiveVoiceConnection, playVoiceTestTone, type VoiceEvent } from '@/lib/live-voice';

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
  const [muted, setMuted] = useState(false);
  const [working, setWorking] = useState(false);
  const [error, setError] = useState('');
  const [playing, setPlaying] = useState(false);
  const [audioHint, setAudioHint] = useState('');
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
    setState('connecting'); setError(''); setMuted(false); setPlaying(false);
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
    {!active && <button type="button" className="live-voice__test" onClick={() => {
      setAudioHint(''); void playVoiceTestTone().then(() => setAudioHint('Se non hai sentito il suono, controlla volume, uscita audio e silenziamento della scheda.')).catch(reason => setAudioHint(reason instanceof Error ? reason.message : 'Audio non disponibile.'));
    }}>Prova audio</button>}
    {active && <span className="live-voice__audio" role="status">{playing ? 'Audio in riproduzione' : working ? 'Elaboro la richiesta…' : 'Audio pronto'}</span>}
    <details className="live-voice__privacy"><summary>Informazioni sulla voce AI</summary><p>Il microfono resta aperto durante la sessione. Le parole vengono inviate subito e salvate in questa chat; le trascrizioni possono contenere errori. LAGGENTE non conserva l’audio.</p></details>
    {audioHint && <p role="status">{audioHint}</p>}
    {error && <p role="alert">{error}</p>}
  </section>;
}
