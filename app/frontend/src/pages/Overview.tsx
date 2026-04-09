import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { Users, ListTodo, Target, CheckCircle, Clock, ArrowRight } from 'lucide-react';
import StatCard from '../components/ui/StatCard';
import StatusBadge from '../components/ui/StatusBadge';
import { getStats, getTasks, getApprovals, getAuditLogs,
  type Stats, type Task, type Approval, type AuditLogEntry } from '../api/client';

export default function Overview() {
  const [stats, setStats] = useState<Stats | null>(null);
  const [overdueTasks, setOverdueTasks] = useState<Task[]>([]);
  const [pendingApprovals, setPendingApprovals] = useState<Approval[]>([]);
  const [recentLogs, setRecentLogs] = useState<AuditLogEntry[]>([]);

  useEffect(() => {
    Promise.all([
      getStats().catch(() => null),
      getTasks({ status: 'overdue' }).catch(() => []),
      getApprovals({ status: 'pending' }).catch(() => []),
      getAuditLogs({ limit: '15' }).catch(() => []),
    ]).then(([s, ot, pa, al]) => {
      if (s) setStats(s);
      setOverdueTasks(Array.isArray(ot) ? ot.slice(0, 5) : []);
      setPendingApprovals(Array.isArray(pa) ? pa.slice(0, 5) : []);
      setRecentLogs(Array.isArray(al) ? al : []);
    });
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

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <div className="rounded-card border border-border bg-surface-1 overflow-hidden flex flex-col" style={{ minHeight: 380 }}>
          <div className="border-b border-border-subtle px-4 py-3 flex items-center justify-between">
            <h3 className="text-[13px] font-semibold text-txt-1">待处理审批</h3>
            <Link to="/approvals" className="text-[12px] text-accent hover:text-accent-hover flex items-center gap-1 transition-colors">全部 <ArrowRight className="w-3 h-3" /></Link>
          </div>
          <div className="flex-1 overflow-y-auto divide-y divide-border-subtle scrollbar-thin">
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

        <div className="rounded-card border border-border bg-surface-1 overflow-hidden flex flex-col" style={{ minHeight: 380 }}>
          <div className="border-b border-border-subtle px-4 py-3 flex items-center justify-between">
            <h3 className="text-[13px] font-semibold text-txt-1">超期预警</h3>
            <Link to="/tasks" className="text-[12px] text-accent hover:text-accent-hover flex items-center gap-1 transition-colors">任务列表 <ArrowRight className="w-3 h-3" /></Link>
          </div>
          <div className="flex-1 overflow-y-auto divide-y divide-border-subtle scrollbar-thin">
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

        <div className="rounded-card border border-border bg-surface-1 overflow-hidden flex flex-col" style={{ minHeight: 380 }}>
          <div className="border-b border-border-subtle px-4 py-3">
            <h3 className="text-[13px] font-semibold text-txt-1">最近动态</h3>
            <p className="text-[11px] text-txt-4 mt-0.5">审计日志 · 最近 15 条</p>
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
      </div>
    </div>
  );
}
