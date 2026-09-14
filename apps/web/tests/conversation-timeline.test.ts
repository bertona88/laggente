import { describe, expect, it } from 'vitest';
import { conversationTimeline } from '../lib/conversation-timeline';
import type { ConversationMessage } from '../lib/types';
const piece = (id: string, text: string, start: number, end: number, session = 'voice-1'): ConversationMessage => ({
 id, content: text, content_type: 'voice_transcript', author_type: 'studio_assistant', author_name: 'AI',
 created_at: new Date(start).toISOString(), voice_session_id: session,
 voice_fragments: [{event_id: id, delta: text, start_ms: start, end_ms: end}],
});
describe('unified voice timeline', () => {
 it('joins fragments across persistence batches and deduplicates live echoes', () => {
   const one = piece('a','Una frase ',0,500); const two = piece('b','completa.',510,900);
   const result = conversationTimeline([one,two,one]);
   expect(result).toHaveLength(1); expect(result[0].content).toBe('Una frase completa.');
   expect(one.content).toBe('Una frase ');
 });
 it('preserves speaker changes and distinct sessions', () => {
   const one = piece('a','Ciao',0,500); const user = {...piece('b','Salve',600,900), author_type:'professional' as const};
   expect(conversationTimeline([one,user,piece('c','Dimmi',1000,1200)])).toHaveLength(3);
   expect(conversationTimeline([one,piece('b','Ciao',700,900,'voice-2')])).toHaveLength(2);
 });
});
it('keeps tool details from breaking a spoken sentence and treats naive API dates as UTC', () => {
 const first = {...piece('a','Ti presenti come ',0,500), created_at:'2026-09-14T10:00:00'};
 const second = {...piece('b','Mauro.',1000,1500), created_at:'2026-09-14T10:00:01'};
 const result: ConversationMessage = {id:'tool',author_type:'studio_assistant',author_name:'AI',content:'Mauro Rossi',content_type:'voice_result',created_at:'2026-09-14T10:00:00.800'};
 const rows = conversationTimeline([first,result,second]);
 expect(rows).toHaveLength(2); expect(rows[0].content).toBe('Ti presenti come Mauro.');
 expect(rows[0].created_at).toBe('2026-09-14T10:00:00.000Z');expect(rows[1].id).toBe('tool');
});
