import { useEffect, useRef, useState } from 'react';
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
  function stop() {
    setState('stopping'); connection.current?.stop();
  }
  if (!available) return null;
  return <section className={`live-voice${active ? ' live-voice--active' : ''}`} aria-label="Conversazione vocale con l’AI">
    {!active ? <div className="live-voice__controls">
      <button type="button" onClick={start} disabled={props.disabled || props.suspended}>
        <MicIcon /> Parla con l’assistente
      </button>
    </div> : <div className="voice-bar">
      <div className="voice-bar__signal">
        <div className="voice-bar__wave" aria-hidden="true">
          {[.25, .45, .7, .4, .85, 1, .6, .9, .5, .75, .4, .25].map((weight, index) =>
            <i key={index} style={{ height: `${4 + level * weight * 32}px`, opacity: .45 + level * .55 }} />)}
        </div>
        <span role="status">{state === 'connecting' ? 'Mi collego…' : state === 'stopping' ? 'Termino la voce…' : playing ? 'Sto parlando' : working ? 'Ci sto lavorando…' : 'Ti ascolto'}</span>
      </div>
      <button className="voice-bar__end" type="button" autoFocus disabled={state === 'stopping'} onClick={stop}>Termina voce</button>
    </div>}
    {error && <p role="alert">{error}</p>}
  </section>;
}
