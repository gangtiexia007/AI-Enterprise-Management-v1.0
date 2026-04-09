import { useEffect, useState, useRef, useCallback } from 'react';
import { Link } from 'react-router-dom';
import { Users, ListTodo, Target, AlertTriangle, CheckCircle, Clock, Send } from 'lucide-react';
import StatCard from '../components/ui/StatCard';
import { getStats, getTasks, getGoals, getApprovals, getAuditLogs, chatWithAgent, getAgentHistory,
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
    try {
      const reply = await chatWithAgent(content);
      setMessages(prev => [...prev, reply]);
    } catch {
      setMessages(prev => [...prev, { role: 'assistant', content: '请求失败' }]);
    }
    setChatLoading(false);
  }, []);

  const s = stats || { total_tasks: 0, overdue_tasks: 0, pending_tasks: 0, completed_tasks: 0, in_progress_tasks: 0, goal_progress: 0, avg_kpi_score: 0, knowledge_count: 0, employee_count: 0, pending_approvals: 0 };
  const completionRate = s.total_tasks > 0 ? Math.round(s.completed_tasks / s.total_tasks * 100) : 0;

  return (
    <div className="space-y-6">
      {/* Stat Cards */}
      <div className="grid grid-cols-2 sm:grid-cols-3 xl:grid-cols-6 gap-3">
        <StatCard label="员工总数" value={s.employee_count} subtitle="当前在册" borderColor="border-l-blue-500"
          icon={<Users className="w-5 h-5" />} iconBg="bg-blue-50 text-blue-600" href="/employees" />
        <StatCard label="进行中任务" value={s.in_progress_tasks + s.pending_tasks} subtitle="待处理 / 执行中"
          borderColor="border-l-amber-400" valueColor="text-amber-600"
          icon={<ListTodo className="w-5 h-5" />} iconBg="bg-amber-50 text-amber-600" href="/tasks" />
        <StatCard label="待审批" value={s.pending_approvals}
          subtitle="进入审批中心"
          borderColor={s.pending_approvals > 0 ? 'border-l-red-500' : 'border-l-gray-300'}
          valueColor={s.pending_approvals > 0 ? 'text-red-600' : 'text-gray-800'}
          icon={<CheckCircle className="w-5 h-5" />} iconBg="bg-gray-100 text-gray-600" href="/approvals" />
        <StatCard label="目标达成率" value={`${s.goal_progress}%`} borderColor="border-l-emerald-500"
          valueColor="text-emerald-700" progress={s.goal_progress} progressColor="bg-emerald-500"
          icon={<Target className="w-5 h-5" />} iconBg="bg-emerald-50 text-emerald-600" />
        <StatCard label="任务完成率" value={`${completionRate}%`} borderColor="border-l-indigo-500"
          valueColor="text-indigo-700" progress={completionRate} progressColor="bg-indigo-500"
          icon={<CheckCircle className="w-5 h-5" />} iconBg="bg-indigo-50 text-indigo-600" />
        <StatCard label="超期任务" value={s.overdue_tasks}
          subtitle="未结案且已过截止"
          borderColor={s.overdue_tasks > 0 ? 'border-l-red-600' : 'border-l-slate-300'}
          valueColor={s.overdue_tasks > 0 ? 'text-red-600' : 'text-gray-800'}
          icon={<Clock className="w-5 h-5" />}
          iconBg={s.overdue_tasks > 0 ? 'bg-red-50 text-red-600' : 'bg-slate-100 text-slate-500'} href="/tasks" />
      </div>

      {/* Approvals + Overdue */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <div className="rounded-lg border border-gray-200 bg-white shadow-sm overflow-hidden">
          <div className="border-b border-gray-200 px-4 py-3 flex items-center justify-between bg-gray-50/80">
            <h3 className="text-sm font-semibold text-gray-800">待处理审批</h3>
            <Link to="/approvals" className="text-xs text-brand-600 hover:text-brand-800 font-medium">全部</Link>
          </div>
          <div className="divide-y divide-gray-100">
            {pendingApprovals.length > 0 ? pendingApprovals.map((a) => (
              <div key={a.id} className="px-4 py-3 hover:bg-gray-50/80">
                <div className="text-sm font-medium text-gray-800">{a.title}</div>
                <div className="mt-1 flex items-center gap-2">
                  <span className={`inline-flex px-1.5 py-0.5 rounded text-[10px] font-semibold ${
                    a.priority && a.priority <= 1 ? 'bg-red-100 text-red-800' : a.priority === 2 ? 'bg-amber-100 text-amber-800' : 'bg-slate-100 text-slate-600'
                  }`}>
                    优先级 {a.priority && a.priority <= 1 ? '高' : a.priority === 2 ? '中' : '低'}
                  </span>
                  <span className="text-xs text-gray-400">{a.created_at?.slice(0, 16)}</span>
                </div>
              </div>
            )) : (
              <div className="px-4 py-10 text-center text-sm text-gray-400">暂无待处理审批</div>
            )}
          </div>
        </div>

        <div className="rounded-lg border border-gray-200 bg-white shadow-sm overflow-hidden">
          <div className="border-b border-gray-200 px-4 py-3 flex items-center justify-between bg-gray-50/80">
            <h3 className="text-sm font-semibold text-gray-800">超期预警</h3>
            <Link to="/tasks" className="text-xs text-brand-600 hover:text-brand-800 font-medium">任务列表</Link>
          </div>
          <div className="divide-y divide-gray-100">
            {overdueTasks.length > 0 ? overdueTasks.map((t) => (
              <div key={t.id} className="flex items-start justify-between gap-3 px-4 py-3 hover:bg-red-50/50">
                <div className="min-w-0">
                  <div className="text-sm font-medium text-gray-800 truncate">{t.title}</div>
                  <div className="text-xs text-gray-500 mt-1">{t.assignee_name || '未指派'}</div>
                </div>
                <div className="text-xs text-red-600 font-medium whitespace-nowrap flex-shrink-0">{t.deadline}</div>
              </div>
            )) : (
              <div className="px-4 py-10 text-center text-sm text-gray-400">暂无超期任务</div>
            )}
          </div>
        </div>
      </div>

      {/* Activity + Chat */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <div className="lg:col-span-1 rounded-lg border border-gray-200 bg-white shadow-sm flex flex-col" style={{ minHeight: 420 }}>
          <div className="border-b border-gray-200 px-4 py-3 bg-gray-50/80">
            <h3 className="text-sm font-semibold text-gray-800">最近动态</h3>
            <p className="text-xs text-gray-400 mt-0.5">审计日志 · 最近 10 条</p>
          </div>
          <div className="flex-1 overflow-y-auto divide-y divide-gray-100 scrollbar-thin">
            {recentLogs.length > 0 ? recentLogs.map((log) => (
              <div key={log.id} className="px-4 py-2.5 text-sm">
                <div className="text-xs text-gray-400 font-mono">{log.created_at?.slice(0, 19)}</div>
                <div className="mt-1 text-gray-800">
                  <span className="font-medium text-gray-900">{log.actor || 'system'}</span>
                  <span className="text-gray-500 mx-1">·</span>
                  <span>{log.action}</span>
                </div>
              </div>
            )) : (
              <div className="px-4 py-12 text-center text-sm text-gray-400">暂无审计记录</div>
            )}
          </div>
        </div>

        <div className="lg:col-span-2 rounded-lg border border-gray-200 bg-white flex flex-col shadow-sm" style={{ minHeight: 420 }}>
          <div className="flex items-center justify-between border-b border-gray-200 px-4 py-2.5 bg-gray-50/50">
            <h3 className="text-sm font-semibold text-gray-800">AI 对话</h3>
            <div className="flex items-center gap-1.5">
              <div className="h-2 w-2 rounded-full bg-green-500" />
              <span className="text-xs text-gray-400">在线</span>
            </div>
          </div>

          <div className="flex-1 overflow-y-auto p-4 space-y-3 scrollbar-thin">
            {messages.map((msg, i) => (
              <div key={i} className={msg.role === 'user' ? 'flex justify-end' : 'flex justify-start'}>
                <div className={`max-w-[80%] rounded-lg px-3 py-2 text-sm whitespace-pre-wrap ${
                  msg.role === 'user' ? 'bg-brand-600 text-white' : 'bg-gray-100 text-gray-800'
                }`}>
                  {msg.content}
                </div>
              </div>
            ))}
            {chatLoading && (
              <div className="flex justify-start">
                <div className="bg-gray-100 rounded-lg px-3 py-2 text-sm text-gray-500">正在思考...</div>
              </div>
            )}
            <div ref={messagesEnd} />
          </div>

          <div className="border-t border-gray-200 p-3">
            <div className="flex flex-wrap gap-1.5 mb-2">
              {['/今日待办', '/逾期', '/团队进度', '/日报'].map((cmd) => (
                <button key={cmd} onClick={() => sendChat(cmd)}
                  className="px-2 py-0.5 text-xs border border-gray-200 rounded text-gray-500 hover:border-brand-300 hover:text-brand-600">
                  {cmd.replace('/', '')}
                </button>
              ))}
            </div>
            <form onSubmit={(e) => { e.preventDefault(); sendChat(chatInput); }} className="flex gap-2">
              <input type="text" value={chatInput} onChange={(e) => setChatInput(e.target.value)}
                placeholder="输入消息或指令..."
                className="flex-1 rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-brand-500 focus:ring-1 focus:ring-brand-500 outline-none" />
              <button type="submit" disabled={!chatInput.trim() || chatLoading}
                className="px-4 py-2 text-sm bg-brand-600 text-white rounded-md hover:bg-brand-700 disabled:opacity-50">
                <Send className="w-4 h-4" />
              </button>
            </form>
          </div>
        </div>
      </div>
    </div>
  );
}
