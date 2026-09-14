import { apiDate } from './format';
import type { ConversationMessage } from './types';
import type { VoiceEvent } from './live-voice';

export function voiceMessage(event: Extract<VoiceEvent, {type: 'transcript'}>, studio: boolean): ConversationMessage {
  return { id: event.event_id, author_type: event.speaker === 'user' ? (studio ? 'professional' : 'visitor') : (studio ? 'studio_assistant' : 'public_assistant'),
    author_name: event.speaker === 'user' ? 'Tu' : 'Assistente AI', content: event.delta,
    created_at: event.created_at, content_type: 'voice_transcript', voice_session_id: event.session_id,
    voice_fragments: [{ event_id: event.event_id, delta: event.delta, start_ms: event.start_ms, end_ms: event.end_ms }] };
}

// Group original timed fragments for display only; authored records remain unchanged.
export function conversationTimeline(messages: ConversationMessage[]): ConversationMessage[] {
  const fragments = new Map<string, ConversationMessage>();
  for (const message of messages) {
    if (!message.voice_fragments?.length) { fragments.set(message.id, message); continue; }
    const origin = apiDate(message.created_at).getTime() - Math.min(...message.voice_fragments.map(f => f.start_ms));
    for (const f of message.voice_fragments) fragments.set(`${message.voice_session_id}:${f.event_id}`, {
      ...message, id: `${message.voice_session_id}:${f.event_id}`, content: f.delta,
      created_at: new Date(origin + f.start_ms).toISOString(), voice_fragments: [f],
    });
  }
  const sorted = [...fragments.values()].sort((a,b) => apiDate(a.created_at).getTime() - apiDate(b.created_at).getTime());
  const grouped: ConversationMessage[] = [];
  const results: ConversationMessage[] = [];
  for (const message of sorted) {
    if (message.content_type === "voice_result") { results.push(message); continue; }
    const previous = grouped.at(-1);
    const last = previous?.voice_fragments?.at(-1);
    const first = message.voice_fragments?.[0];
    if (previous && last && first && previous.author_type === message.author_type && previous.voice_session_id === message.voice_session_id && (first.start_ms - last.end_ms < 2000 || (!/[.!?。]\s*$/.test(previous.content) && first.start_ms - last.end_ms < 15000))) {
      previous.content += message.content;
      previous.voice_fragments = [...previous.voice_fragments!, ...message.voice_fragments!];
    } else grouped.push({...message});
  }
  for (const result of results) {
    const time = apiDate(result.created_at).getTime();
    const index = grouped.findIndex(message => {
      if (!message.author_type.endsWith('assistant') || message.content_type !== 'voice_transcript') return false;
      const parts = message.voice_fragments || [];
      const duration = parts.length ? parts.at(-1)!.end_ms - parts[0].start_ms : 0;
      return apiDate(message.created_at).getTime() + duration >= time;
    });
    if (index >= 0) grouped.splice(index + 1, 0, result);
    else grouped.push(result);
  }
  return grouped;
}
