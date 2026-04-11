import { useEffect, useState, useCallback } from 'react';
import { Brain, Shield, Target, AlertTriangle, Clock, Send, ChevronRight } from 'lucide-react';
import StatCard from '../components/ui/StatCard';
import { getMultiAgentRuns, multiAgentChat, type MultiAgentRun } from '../api/client';

const SUFFICIENCY_STYLE: Record<string, { bg: string; text: string }> = {
  sufficient: { bg: 'bg-emerald-50', text: 'text-emerald-700' },
  partial: { bg: 'bg-amber-50', text: 'text-amber-700' },
  insufficient: { bg: 'bg-red-50', text: 'text-red-600' },
};

export default function MultiAgentDashboard() {
  const [runs, setRuns] = useState<MultiAgentRun[]>([]);
  const [loading, setLoading] = useState(true);
  const [chatInput, setChatInput] = useState('');
  const [sending, setSending] = useState(false);
  const [chatReply, setChatReply] = useState<{
    response: string; run_id: string; task_type: string;
  } | null>(null);
  const [expandedRun, setExpandedRun] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const data = await getMultiAgentRuns({ limit: 20 }) as unknown as { total: number; items: MultiAgentRun[] };
      setRuns(Array.isArray(data) ? data : (data?.items || []));
    } catch { setRuns([]); }
    setLoading(false);
  }, []);

  useEffect(() => { load(); }, [load]);

  const stats = {
    pending: runs.filter(r => r.data_sufficiency === 'partial').length,
    blocked: runs.filter(r => r.data_sufficiency === 'insufficient').length,
    completed: runs.filter(r => r.data_sufficiency === 'sufficient').length,
    highRisk: runs.filter(r => r.task_type === 'risk_check' || r.task_type === 'compliance_check').length,
  };

  const handleSend = async () => {
    if (!chatInput.trim() || sending) return;
    setSending(true);
    setChatReply(null);
    try {
      const res = await multiAgentChat(chatInput.trim());
      setChatReply(res);
      setChatInput('');
      load();
    } catch (e) {
      setChatReply({ response: `Error: ${e instanceof Error ? e.message : String(e)}`, run_id: '', task_type: '' });
    }
    setSending(false);
  };

  const parseAgentsCalled = (raw: string | string[]): string[] => {
    if (Array.isArray(raw)) return raw;
    if (!raw) return [];
    try { return JSON.parse(raw); } catch { return raw.split(','); }
  };

  return (
    <div className="space-y-5">
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <StatCard label="待处理任务" value={stats.pending} icon={<Target className="w-4 h-4" />} />
        <StatCard label="数据不足" value={stats.blocked} accent="text-amber-600" icon={<AlertTriangle className="w-4 h-4" />} />
        <StatCard label="已完成" value={stats.completed} accent="text-emerald-700" icon={<Shield className="w-4 h-4" />} />
        <StatCard label="风控任务" value={stats.highRisk} accent="text-red-600" icon={<Brain className="w-4 h-4" />} />
      </div>

      {loading ? (
        <div className="text-center py-12 text-txt-4 text-[13px]">加载中...</div>
      ) : (
        <div className="rounded-card border border-border bg-surface-1 overflow-hidden">
          <div className="border-b border-border-subtle px-4 py-3">
            <h3 className="text-[13px] font-semibold text-txt-1">最近运行记录</h3>
          </div>
          <table className="min-w-full text-[13px]">
            <thead>
              <tr className="border-b border-border text-left text-[11px] font-medium text-txt-4 uppercase tracking-wider bg-surface-0/60">
                <th className="px-4 py-3">Run ID</th>
                <th className="px-4 py-3">任务类型</th>
                <th className="px-4 py-3">Agent 链</th>
                <th className="px-4 py-3">数据充分性</th>
                <th className="px-4 py-3">耗时</th>
                <th className="px-4 py-3">时间</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border-subtle">
              {runs.map(r => {
                const agents = parseAgentsCalled(r.agents_called);
                const suf = SUFFICIENCY_STYLE[r.data_sufficiency] || SUFFICIENCY_STYLE.partial;
                const isExpanded = expandedRun === r.run_id;
                return (
                  <tr key={r.id} className="hover:bg-surface-3/40 transition-colors cursor-pointer" onClick={() => setExpandedRun(isExpanded ? null : r.run_id)}>
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-1">
                        <ChevronRight className={`w-3 h-3 text-txt-4 transition-transform ${isExpanded ? 'rotate-90' : ''}`} />
                        <span className="font-mono text-[12px] text-accent">{r.run_id.slice(0, 8)}</span>
                      </div>
                      {isExpanded && r.final_output && (
                        <div className="mt-2 p-3 bg-surface-0 rounded-btn text-[12px] text-txt-3 whitespace-pre-wrap max-h-40 overflow-y-auto">
                          {r.final_output.slice(0, 500)}{r.final_output.length > 500 ? '...' : ''}
                        </div>
                      )}
                    </td>
                    <td className="px-4 py-3">
                      <span className="inline-block px-2 py-0.5 text-[11px] rounded-full bg-indigo-50 text-indigo-700 dark:bg-indigo-900/30 dark:text-indigo-300">
                        {r.task_type || r.route_name}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-1 flex-wrap">
                        {agents.slice(0, 4).map((a, i) => (
                          <span key={i} className="inline-block px-1.5 py-0.5 text-[10px] rounded-micro bg-surface-3 text-txt-3">{a}</span>
                        ))}
                        {agents.length > 4 && <span className="text-[10px] text-txt-4">+{agents.length - 4}</span>}
                      </div>
                    </td>
                    <td className="px-4 py-3">
                      <span className={`inline-flex items-center px-1.5 py-0.5 rounded-micro text-[11px] font-medium ${suf.bg} ${suf.text}`}>
                        {r.data_sufficiency || '-'}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-txt-3">
                      <div className="flex items-center gap-1">
                        <Clock className="w-3 h-3" />
                        {r.duration_ms ? `${(r.duration_ms / 1000).toFixed(1)}s` : '-'}
                      </div>
                    </td>
                    <td className="px-4 py-3 text-txt-4 text-[12px]">{r.created_at?.slice(0, 16)}</td>
                  </tr>
                );
              })}
              {runs.length === 0 && (
                <tr><td colSpan={6} className="px-4 py-12 text-center text-txt-4 text-[13px]">暂无运行记录</td></tr>
              )}
            </tbody>
          </table>
        </div>
      )}

      {chatReply && (
        <div className="rounded-card border border-border bg-surface-1 overflow-hidden">
          <div className="border-b border-border-subtle px-4 py-3 flex items-center justify-between">
            <h3 className="text-[13px] font-semibold text-txt-1">Agent 响应</h3>
            <div className="flex items-center gap-2">
              {chatReply.task_type && (
                <span className="inline-block px-2 py-0.5 text-[11px] rounded-full bg-indigo-50 text-indigo-700">{chatReply.task_type}</span>
              )}
              {chatReply.run_id && (
                <span className="font-mono text-[11px] text-txt-4">{chatReply.run_id.slice(0, 8)}</span>
              )}
            </div>
          </div>
          <div className="px-4 py-3">
            <div className="text-[13px] text-txt-2 whitespace-pre-wrap">{chatReply.response}</div>
          </div>
        </div>
      )}

      <div className="rounded-card border border-border bg-surface-1 p-4">
        <div className="flex items-end gap-3">
          <div className="flex-1">
            <label className="block text-[12px] font-medium text-txt-3 mb-1.5">向 POD Agent 发送指令</label>
            <textarea
              value={chatInput}
              onChange={e => setChatInput(e.target.value)}
              onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSend(); } }}
              placeholder="输入指令，例如：帮我分析 Shopee PH 宠物赛道的可行性"
              rows={2}
              className="w-full rounded-btn border border-border bg-surface-0 px-3 py-2 text-[13px] text-txt-1 placeholder:text-txt-4 focus:border-accent/40 focus:outline-none transition-colors resize-none"
            />
          </div>
          <button
            onClick={handleSend}
            disabled={sending || !chatInput.trim()}
            className="flex items-center gap-1.5 px-4 py-2 text-[13px] font-medium bg-accent text-white rounded-btn hover:bg-accent-hover disabled:opacity-40 transition-colors"
          >
            <Send className="w-3.5 h-3.5" />
            {sending ? '发送中...' : '发送'}
          </button>
        </div>
      </div>
    </div>
  );
}
