import { useState, useEffect, useRef, useCallback } from 'react';
import { X, Send } from 'lucide-react';
import { chatWithAgent, getAgentHistory, ChatMessage } from '../api/client';

interface ChatDrawerProps {
  open: boolean;
  onClose: () => void;
}

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
  const messagesEnd = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => messagesEnd.current?.scrollIntoView({ behavior: 'smooth' });

  const loadHistory = useCallback(async () => {
    try {
      const hist = await getAgentHistory();
      setMessages(Array.isArray(hist) ? hist : []);
    } catch { /* ignore */ }
  }, []);

  useEffect(() => {
    if (open) loadHistory();
  }, [open, loadHistory]);

  useEffect(() => { scrollToBottom(); }, [messages]);

  const send = async (content: string) => {
    if (!content.trim()) return;
    const userMsg: ChatMessage = { role: 'user', content };
    setMessages((prev) => [...prev, userMsg]);
    setInput('');
    setLoading(true);
    try {
      const reply = await chatWithAgent(content);
      setMessages((prev) => [...prev, reply]);
    } catch {
      setMessages((prev) => [...prev, { role: 'assistant', content: '请求失败，请稍后重试' }]);
    }
    setLoading(false);
  };

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-40 flex justify-end">
      <div className="absolute inset-0 bg-black/20" onClick={onClose} />
      <div className="relative w-96 max-w-full bg-white border-l border-gray-200 flex flex-col shadow-xl">
        <div className="flex items-center justify-between border-b border-gray-200 px-4 py-3 bg-gray-50/50">
          <h3 className="text-sm font-semibold text-gray-800">AI 对话</h3>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600">
            <X className="w-4 h-4" />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto p-4 space-y-3 scrollbar-thin">
          {messages.map((msg, i) => (
            <div key={i} className={msg.role === 'user' ? 'flex justify-end' : 'flex justify-start'}>
              <div className={`max-w-[85%] rounded-lg px-3 py-2 text-sm whitespace-pre-wrap ${
                msg.role === 'user'
                  ? 'bg-brand-600 text-white'
                  : 'bg-gray-100 text-gray-800'
              }`}>
                {msg.content}
              </div>
            </div>
          ))}
          {loading && (
            <div className="flex justify-start">
              <div className="bg-gray-100 text-gray-500 rounded-lg px-3 py-2 text-sm">
                正在思考...
              </div>
            </div>
          )}
          <div ref={messagesEnd} />
        </div>

        <div className="border-t border-gray-200 p-3 space-y-2">
          <div className="flex flex-wrap gap-1.5">
            {QUICK_COMMANDS.map((qc) => (
              <button
                key={qc.cmd}
                onClick={() => send(qc.cmd)}
                className="px-2 py-0.5 text-xs border border-gray-200 rounded text-gray-500 hover:border-brand-300 hover:text-brand-600"
              >
                {qc.label}
              </button>
            ))}
          </div>
          <form onSubmit={(e) => { e.preventDefault(); send(input); }} className="flex gap-2">
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="输入消息或指令..."
              className="flex-1 rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-brand-500 focus:ring-1 focus:ring-brand-500 outline-none"
            />
            <button
              type="submit"
              disabled={!input.trim() || loading}
              className="px-3 py-2 text-sm bg-brand-600 text-white rounded-md hover:bg-brand-700 disabled:opacity-50"
            >
              <Send className="w-4 h-4" />
            </button>
          </form>
        </div>
      </div>
    </div>
  );
}
