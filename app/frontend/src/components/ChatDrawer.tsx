import { useState, useEffect, useRef, useCallback } from 'react';
import { X, Send } from 'lucide-react';
import { chatWithAgent, chatWithAgentStream, getAgentHistory, multiAgentChat, ChatMessage } from '../api/client';

interface ChatDrawerProps { open: boolean; onClose: () => void; }

const QUICK_COMMANDS = [
  { label: '今日待办', cmd: '/今日待办' },
  { label: '逾期任务', cmd: '/逾期' },
  { label: '团队进度', cmd: '/团队进度' },
  { label: '日报', cmd: '/日报' },
  { label: '催办', cmd: '/催办' },
];

export default function ChatDrawer({ open, onClose }: ChatDrawerProps) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [agentMode, setAgentMode] = useState<'full' | 'multi_agent'>('full');
  const messagesEnd = useRef<HTMLDivElement>(null);

  const loadHistory = useCallback(async () => {
    try { const hist = await getAgentHistory(); setMessages(Array.isArray(hist) ? hist : []); } catch {}
  }, []);

  useEffect(() => { if (open) loadHistory(); }, [open, loadHistory]);
  useEffect(() => { messagesEnd.current?.scrollIntoView({ behavior: 'smooth' }); }, [messages]);

  const send = async (content: string) => {
    if (!content.trim()) return;
    setMessages(prev => [...prev, { role: 'user', content }]);
    setInput('');
    setLoading(true);
    try {
      if (agentMode === 'multi_agent') {
        const res = await multiAgentChat(content);
        setMessages(prev => [...prev, { role: 'assistant', content: res.response }]);
        setLoading(false);
      } else {
        setMessages(prev => [...prev, { role: 'assistant', content: '' }]);
        await chatWithAgentStream(
          content,
          (chunk) => {
            setMessages(prev => {
              const updated = [...prev];
              const last = updated[updated.length - 1];
              if (last && last.role === 'assistant') {
                updated[updated.length - 1] = { ...last, content: last.content + chunk };
              }
              return updated;
            });
          },
          () => setLoading(false),
        );
      }
    } catch {
      setMessages(prev => {
        const last = prev[prev.length - 1];
        if (last && last.role === 'assistant' && !last.content) {
          return [...prev.slice(0, -1), { role: 'assistant' as const, content: '请求失败，请稍后重试' }];
        }
        return [...prev, { role: 'assistant' as const, content: '请求失败，请稍后重试' }];
      });
      setLoading(false);
    }
  };

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-40 flex justify-end">
      <div className="absolute inset-0 bg-black/10" onClick={onClose} />
      <div className="relative w-96 max-w-full bg-surface-1 border-l border-border flex flex-col shadow-xl">
        <div className="flex items-center justify-between border-b border-border-subtle px-4 py-3">
          <div className="flex items-center gap-2">
            <h3 className="text-[14px] font-semibold text-txt-1">AI 对话</h3>
            <div className="flex items-center gap-1">
              <div className="h-1.5 w-1.5 rounded-full bg-emerald" />
              <span className="text-[11px] text-txt-4">在线</span>
            </div>
          </div>
          <button onClick={onClose} className="text-txt-4 hover:text-txt-2 transition-colors rounded-full p-1 hover:bg-surface-3">
            <X className="w-4 h-4" />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto p-4 space-y-3 scrollbar-thin">
          {messages.map((msg, i) => (
            <div key={i} className={msg.role === 'user' ? 'flex justify-end' : 'flex justify-start'}>
              <div className={`max-w-[85%] rounded-card px-3 py-2 text-[13px] leading-relaxed whitespace-pre-wrap ${
                msg.role === 'user' ? 'bg-accent text-white' : 'bg-surface-3 text-txt-1 border border-border-subtle'
              }`}>{msg.content}</div>
            </div>
          ))}
          {loading && (
            <div className="flex justify-start">
              <div className="bg-surface-3 border border-border-subtle text-txt-3 rounded-card px-3 py-2 text-[13px]">
                <span className="animate-pulse">正在思考...</span>
              </div>
            </div>
          )}
          <div ref={messagesEnd} />
        </div>

        <div className="border-t border-border-subtle p-3 space-y-2">
          <div className="flex gap-1.5 mb-1">
            {([['full', '通用模式'], ['multi_agent', 'POD Agent']] as const).map(([mode, label]) => (
              <button key={mode} onClick={() => setAgentMode(mode)}
                className={`px-2.5 py-1 text-[11px] font-medium rounded-pill transition-colors ${
                  agentMode === mode
                    ? 'bg-accent text-white'
                    : 'border border-border text-txt-3 hover:text-accent hover:border-accent/30'
                }`}>
                {label}
              </button>
            ))}
          </div>
          <div className="flex flex-wrap gap-1.5">
            {QUICK_COMMANDS.map(qc => (
              <button key={qc.cmd} onClick={() => send(qc.cmd)}
                className="px-2 py-0.5 text-[11px] font-medium border border-border rounded-pill text-txt-3 hover:text-accent hover:border-accent/30 transition-colors">
                {qc.label}
              </button>
            ))}
          </div>
          <form onSubmit={e => { e.preventDefault(); send(input); }} className="flex gap-2">
            <input type="text" value={input} onChange={e => setInput(e.target.value)} placeholder="输入消息或指令..."
              className="flex-1 rounded-btn border border-border bg-surface-1 px-3 py-2 text-[13px] text-txt-1 placeholder:text-txt-4 focus:border-accent/40 focus:outline-none transition-colors" />
            <button type="submit" disabled={!input.trim() || loading}
              className="px-3 py-2 bg-accent text-white rounded-btn hover:bg-accent-hover disabled:opacity-40 transition-colors">
              <Send className="w-3.5 h-3.5" />
            </button>
          </form>
        </div>
      </div>
    </div>
  );
}
