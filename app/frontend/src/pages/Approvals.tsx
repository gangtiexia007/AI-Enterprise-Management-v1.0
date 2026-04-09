import { useEffect, useState, useCallback } from 'react';
import { CheckCircle, XCircle, Clock } from 'lucide-react';
import StatCard from '../components/ui/StatCard';
import FilterChips from '../components/ui/FilterChips';
import StatusBadge from '../components/ui/StatusBadge';
import { getApprovals, approveApproval, rejectApproval, type Approval } from '../api/client';

const STATUS_FILTERS = [
  { label: '全部', value: '' },
  { label: '待审批', value: 'pending' },
  { label: '已通过', value: 'approved' },
  { label: '已驳回', value: 'rejected' },
];

export default function Approvals() {
  const [approvals, setApprovals] = useState<Approval[]>([]);
  const [loading, setLoading] = useState(true);
  const [filterStatus, setFilterStatus] = useState('');
  const [selectedId, setSelectedId] = useState<number | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const params: Record<string, string> = {};
      if (filterStatus) params.status = filterStatus;
      const a = await getApprovals(params);
      setApprovals(Array.isArray(a) ? a : []);
    } catch { setApprovals([]); }
    setLoading(false);
  }, [filterStatus]);

  useEffect(() => { load(); }, [load]);

  const selected = approvals.find(a => a.id === selectedId);
  const stats = {
    pending: approvals.filter(a => a.status === 'pending').length,
    approved: approvals.filter(a => a.status === 'approved').length,
    rejected: approvals.filter(a => a.status === 'rejected').length,
  };

  const handleApprove = async (id: number) => { await approveApproval(id); load(); };
  const handleReject = async (id: number) => { if (confirm('确认驳回？')) { await rejectApproval(id); load(); } };

  return (
    <div className="space-y-5">
      <div className="grid grid-cols-2 lg:grid-cols-3 gap-3">
        <StatCard label="待审批" value={stats.pending}
          accent={stats.pending > 0 ? 'text-red-400' : undefined}
          icon={<Clock className="w-4 h-4" />} />
        <StatCard label="已通过" value={stats.approved} accent="text-emerald"
          icon={<CheckCircle className="w-4 h-4" />} />
        <StatCard label="已驳回" value={stats.rejected} accent="text-red-400"
          icon={<XCircle className="w-4 h-4" />} />
      </div>

      <FilterChips label="状态" options={STATUS_FILTERS} value={filterStatus} onChange={setFilterStatus} />

      {loading ? (
        <div className="text-center py-12 text-txt-4 text-[13px]">加载中...</div>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-5 gap-4" style={{ minHeight: 500 }}>
          <div className="lg:col-span-2 rounded-card border border-border overflow-hidden flex flex-col">
            <div className="border-b border-border px-4 py-3">
              <h3 className="text-[13px] font-semibold text-txt-1">审批列表</h3>
            </div>
            <div className="flex-1 overflow-y-auto divide-y divide-border scrollbar-thin" style={{ maxHeight: 600 }}>
              {approvals.length > 0 ? approvals.map((a) => (
                <div key={a.id}
                  onClick={() => setSelectedId(a.id)}
                  className={`px-4 py-3 cursor-pointer hover:bg-[rgba(255,255,255,0.02)] transition-colors ${
                    selectedId === a.id ? 'bg-[rgba(255,255,255,0.04)] border-l-2 border-l-accent-light' : ''
                  }`}>
                  <div className="text-[13px] font-medium text-txt-2 line-clamp-2">{a.title}</div>
                  <div className="mt-1.5 flex items-center gap-2">
                    <StatusBadge status={a.status} />
                    <StatusBadge status={a.priority && a.priority <= 1 ? 'urgent' : a.priority === 2 ? 'high' : 'normal'} />
                    <span className="text-[11px] text-txt-4">{a.created_at?.slice(0, 16)}</span>
                  </div>
                </div>
              )) : (
                <div className="px-4 py-12 text-center text-[13px] text-txt-4">暂无审批项</div>
              )}
            </div>
          </div>

          <div className="lg:col-span-3 rounded-card border border-border overflow-hidden">
            {selected ? (
              <div className="p-5">
                <div className="mb-4">
                  <h2 className="text-[16px] font-semibold text-txt-1 tracking-tight">{selected.title}</h2>
                  <div className="flex items-center gap-2 mt-2">
                    <StatusBadge status={selected.status} />
                    <span className="text-[11px] text-txt-4">类型: {selected.type}</span>
                    <span className="text-[11px] text-txt-4">创建: {selected.created_at?.slice(0, 16)}</span>
                  </div>
                </div>
                {selected.detail && (
                  <div className="rounded-card bg-[rgba(255,255,255,0.03)] border border-border p-4 text-[13px] text-txt-2 whitespace-pre-wrap mb-4 leading-relaxed">
                    {selected.detail}
                  </div>
                )}
                {selected.resolved_at && (
                  <div className="text-[11px] text-txt-4 mb-4">
                    处理时间: {selected.resolved_at.slice(0, 16)} | 处理人: {selected.resolved_by}
                  </div>
                )}
                {selected.status === 'pending' && (
                  <div className="flex items-center gap-2 pt-4 border-t border-border">
                    <button onClick={() => handleApprove(selected.id)}
                      className="px-4 py-2 text-[13px] font-medium rounded-btn bg-emerald/80 text-white hover:bg-emerald transition-colors">
                      通过
                    </button>
                    <button onClick={() => handleReject(selected.id)}
                      className="px-4 py-2 text-[13px] font-medium rounded-btn bg-red-500/80 text-white hover:bg-red-500 transition-colors">
                      驳回
                    </button>
                  </div>
                )}
              </div>
            ) : (
              <div className="flex items-center justify-center h-full py-20">
                <div className="text-center">
                  <CheckCircle className="w-10 h-10 mx-auto mb-3 text-txt-4" />
                  <div className="text-[13px] text-txt-4">选择左侧审批项查看详情</div>
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
