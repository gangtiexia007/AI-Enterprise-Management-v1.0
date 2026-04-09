import { useEffect, useState, useRef, useCallback } from 'react';
import { Link } from 'react-router-dom';
import { Users, ListTodo, Target, CheckCircle, Clock, Send, ArrowRight } from 'lucide-react';
import StatCard from '../components/ui/StatCard';
import StatusBadge from '../components/ui/StatusBadge';
import { getStats, getTasks, getApprovals, getAuditLogs, chatWithAgent, getAgentHistory,
  type Stats, type Task, type Approval, type AuditLogEntry, type ChatMessage } from '../api/client';

export default function Overview() {
  const [stats, setStats] = useState<Stats | null>(null);
  const [overdueTasks, setOverdueTasks] = useState<Task[]>([]);
  const [pendingApprovals, setPendingApprovals] = useState<Approval[]>([]);
  const [recentLogs, setRecentLogs] = useState<AuditLogEntry[]>([]);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [chatInput, setChatInput] = useState('');
  const [chatLoading, setChatLoading] = useState(false);
  const messagesEnd = useRef<HTMLDivElement>(null);

  useEffect(() => {
    Promise.all([
      getStats().catch(() => null),
      getTasks({ status: 'overdue' }).catch(() => []),
      getApprovals({ status: 'pending' }).catch(() => []),
      getAuditLogs({ limit: '10' }).catch(() => []),
      getAgentHistory().catch(() => []),
    ]).then(([s, ot, pa, al, hist]) => {
      if (s) setStats(s);
      setOverdueTasks(Array.isArray(ot) ? ot.slice(0, 5) : []);
      setPendingApprovals(Array.isArray(pa) ? pa.slice(0, 5) : []);
      setRecentLogs(Array.isArray(al) ? al : []);
      setMessages(Array.isArray(hist) ? hist : []);
    });
  }, []);

  useEffect(() => { messagesEnd.current?.scrollIntoView({ behavior: 'smooth' }); }, [messages]);

  const sendChat = useCallback(async (content: string) => {
    if (!content.trim()) return;
    setMessages(prev => [...prev, { role: 'user', content }]);
    setChatInput('');
    setChatLoading(true);
    try { const reply = await chatWithAgent(content); setMessages(prev => [...prev, reply]); }
    catch { setMessages(prev => [...prev, { role: 'assistant', content: '请求失败' }]); }
    setChatLoading(false);
  }, []);

  const s = stats || { total_tasks: 0, overdue_tasks: 0, pending_tasks: 0, completed_tasks: 0, in_progress_tasks: 0, goal_progress: 0, avg_kpi_score: 0, knowledge_count: 0, employee_count: 0, pending_approvals: 0 };
  const completionRate = s.total_tasks > 0 ? Math.round(s.completed_tasks / s.total_tasks * 100) : 0;

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-2 sm:grid-cols-3 xl:grid-cols-6 gap-3">
        <StatCard label="员工总数" value={s.employee_count} subtitle="当前在册" icon={<Users className="w-4 h-4" />} href="/employees" />
        <StatCard label="进行中任务" value={s.in_progress_tasks + s.pending_tasks} subtitle="待处理 / 执行中" accent="text-amber-600" icon={<ListTodo className="w-4 h-4" />} href="/tasks" />
        <StatCard label="待审批" value={s.pending_approvals} subtitle="进入审批中心" accent={s.pending_approvals > 0 ? 'text-red-600' : undefined} icon={<CheckCircle className="w-4 h-4" />} href="/approvals" />
        <StatCard label="目标达成率" value={`${s.goal_progress}%`} accent="text-emerald-700" progress={s.goal_progress} icon={<Target className="w-4 h-4" />} />
        <StatCard label="任务完成率" value={`${completionRate}%`} accent="text-accent" progress={completionRate} icon={<CheckCircle className="w-4 h-4" />} />
        <StatCard label="超期任务" value={s.overdue_tasks} subtitle="未结案且已过截止" accent={s.overdue_tasks > 0 ? 'text-red-600' : undefined} icon={<Clock className="w-4 h-4" />} href="/tasks" />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <div className="rounded-card border border-border bg-surface-1 overflow-hidden">
          <div className="border-b border-border-subtle px-4 py-3 flex items-center justify-between">
            <h3 className="text-[13px] font-semibold text-txt-1">待处理审批</h3>
            <Link to="/approvals" className="text-[12px] text-accent hover:text-accent-hover flex items-center gap-1 transition-colors">全部 <ArrowRight className="w-3 h-3" /></Link>
          </div>
          <div className="divide-y divide-border-subtle">
            {pendingApprovals.length > 0 ? pendingApprovals.map(a => (
              <div key={a.id} className="px-4 py-3 hover:bg-surface-3/50 transition-colors">
                <div className="text-[13px] font-medium text-txt-1">{a.title}</div>
                <div className="mt-1.5 flex items-center gap-2">
                  <StatusBadge status={a.priority && a.priority <= 1 ? 'urgent' : a.priority === 2 ? 'high' : 'normal'} />
                  <span className="text-[11px] text-txt-4">{a.created_at?.slice(0, 16)}</span>
                </div>
              </div>
            )) : <div className="px-4 py-10 text-center text-[13px] text-txt-4">暂无待处理审批</div>}
          </div>
        </div>

        <div className="rounded-card border border-border bg-surface-1 overflow-hidden">
          <div className="border-b border-border-subtle px-4 py-3 flex items-center justify-between">
            <h3 className="text-[13px] font-semibold text-txt-1">超期预警</h3>
            <Link to="/tasks" className="text-[12px] text-accent hover:text-accent-hover flex items-center gap-1 transition-colors">任务列表 <ArrowRight className="w-3 h-3" /></Link>
          </div>
          <div className="divide-y divide-border-subtle">
            {overdueTasks.length > 0 ? overdueTasks.map(t => (
              <div key={t.id} className="flex items-start justify-between gap-3 px-4 py-3 hover:bg-red-50/50 transition-colors">
                <div className="min-w-0">
                  <div className="text-[13px] font-medium text-txt-1 truncate">{t.title}</div>
                  <div className="text-[11px] text-txt-4 mt-1">{t.assignee_name || '未指派'}</div>
                </div>
                <div className="text-[12px] text-red-600 font-medium whitespace-nowrap flex-shrink-0">{t.deadline}</div>
              </div>
            )) : <div className="px-4 py-10 text-center text-[13px] text-txt-4">暂无超期任务</div>}
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <div className="lg:col-span-1 rounded-card border border-border bg-surface-1 flex flex-col" style={{ minHeight: 420 }}>
          <div className="border-b border-border-subtle px-4 py-3">
            <h3 className="text-[13px] font-semibold text-txt-1">最近动态</h3>
            <p className="text-[11px] text-txt-4 mt-0.5">审计日志 · 最近 10 条</p>
          </div>
          <div className="flex-1 overflow-y-auto divide-y divide-border-subtle scrollbar-thin">
            {recentLogs.length > 0 ? recentLogs.map(log => (
              <div key={log.id} className="px-4 py-2.5">
                <div className="text-[11px] text-txt-4 font-mono">{log.created_at?.slice(0, 19)}</div>
                <div className="mt-1 text-[13px]">
                  <span className="font-medium text-txt-1">{log.actor || 'system'}</span>
                  <span className="text-txt-4 mx-1">·</span>
                  <span className="text-txt-3">{log.action}</span>
                </div>
              </div>
            )) : <div className="px-4 py-12 text-center text-[13px] text-txt-4">暂无审计记录</div>}
          </div>
        </div>

        <div className="lg:col-span-2 rounded-card border border-border bg-surface-1 flex flex-col" style={{ minHeight: 420 }}>
          <div className="flex items-center justify-between border-b border-border-subtle px-4 py-2.5">
            <h3 className="text-[13px] font-semibold text-txt-1">AI 对话</h3>
            <div className="flex items-center gap-1.5"><div className="h-1.5 w-1.5 rounded-full bg-emerald" /><span className="text-[11px] text-txt-4">在线</span></div>
          </div>
          <div className="flex-1 overflow-y-auto p-4 space-y-3 scrollbar-thin">
            {messages.map((msg, i) => (
              <div key={i} className={msg.role === 'user' ? 'flex justify-end' : 'flex justify-start'}>
                <div className={`max-w-[80%] rounded-card px-3 py-2 text-[13px] leading-relaxed whitespace-pre-wrap ${
                  msg.role === 'user' ? 'bg-accent text-white' : 'bg-surface-3 text-txt-1'
                }`}>{msg.content}</div>
              </div>
            ))}
            {chatLoading && <div className="flex justify-start"><div className="bg-surface-3 rounded-card px-3 py-2 text-[13px] text-txt-3 animate-pulse">正在思考...</div></div>}
            <div ref={messagesEnd} />
          </div>
          <div className="border-t border-border-subtle p-3">
            <div className="flex flex-wrap gap-1.5 mb-2">
              {['/今日待办', '/逾期', '/团队进度', '/日报'].map(cmd => (
                <button key={cmd} onClick={() => sendChat(cmd)}
                  className="px-2 py-0.5 text-[11px] font-medium border border-border rounded-pill text-txt-3 hover:text-accent hover:border-accent/30 transition-colors">
                  {cmd.replace('/', '')}
                </button>
              ))}
            </div>
            <form onSubmit={e => { e.preventDefault(); sendChat(chatInput); }} className="flex gap-2">
              <input type="text" value={chatInput} onChange={e => setChatInput(e.target.value)} placeholder="输入消息或指令..."
                className="flex-1 rounded-btn border border-border bg-surface-1 px-3 py-2 text-[13px] text-txt-1 placeholder:text-txt-4 focus:border-accent/40 focus:outline-none transition-colors" />
              <button type="submit" disabled={!chatInput.trim() || chatLoading}
                className="px-4 py-2 bg-accent text-white rounded-btn hover:bg-accent-hover disabled:opacity-40 transition-colors">
                <Send className="w-3.5 h-3.5" />
              </button>
            </form>
          </div>
        </div>
      </div>
    </div>
  );
}
