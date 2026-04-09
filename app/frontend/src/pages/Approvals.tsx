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

  const handleApprove = async (id: number) => {
    await approveApproval(id);
    load();
  };

  const handleReject = async (id: number) => {
    if (confirm('确认驳回？')) {
      await rejectApproval(id);
      load();
    }
  };

  return (
    <div className="space-y-5">
      <div className="grid grid-cols-2 lg:grid-cols-3 gap-3">
        <StatCard label="待审批" value={stats.pending}
          borderColor={stats.pending > 0 ? 'border-l-red-500' : 'border-l-gray-300'}
          valueColor={stats.pending > 0 ? 'text-red-600' : 'text-gray-800'}
          icon={<Clock className="w-5 h-5" />} iconBg="bg-gray-100 text-gray-600" />
        <StatCard label="已通过" value={stats.approved} borderColor="border-l-green-500" valueColor="text-green-600"
          icon={<CheckCircle className="w-5 h-5" />} iconBg="bg-green-50 text-green-600" />
        <StatCard label="已驳回" value={stats.rejected} borderColor="border-l-red-400" valueColor="text-red-500"
          icon={<XCircle className="w-5 h-5" />} iconBg="bg-red-50 text-red-500" />
      </div>

      <FilterChips label="状态" options={STATUS_FILTERS} value={filterStatus} onChange={setFilterStatus} />

      {loading ? (
        <div className="text-center py-12 text-gray-400">加载中...</div>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-5 gap-4" style={{ minHeight: 500 }}>
          {/* List */}
          <div className="lg:col-span-2 rounded-lg border border-gray-200 bg-white shadow-sm overflow-hidden flex flex-col">
            <div className="border-b border-gray-200 px-4 py-3 bg-gray-50/80">
              <h3 className="text-sm font-semibold text-gray-800">审批列表</h3>
            </div>
            <div className="flex-1 overflow-y-auto divide-y divide-gray-100 scrollbar-thin" style={{ maxHeight: 600 }}>
              {approvals.length > 0 ? approvals.map((a) => (
                <div key={a.id}
                  onClick={() => setSelectedId(a.id)}
                  className={`px-4 py-3 cursor-pointer hover:bg-gray-50 ${selectedId === a.id ? 'bg-brand-50/50 border-l-2 border-l-brand-500' : ''}`}>
                  <div className="text-sm font-medium text-gray-800 line-clamp-2">{a.title}</div>
                  <div className="mt-1.5 flex items-center gap-2">
                    <StatusBadge status={a.status} />
                    <span className={`inline-flex px-1.5 py-0.5 rounded text-[10px] font-semibold ${
                      a.priority && a.priority <= 1 ? 'bg-red-100 text-red-800' : a.priority === 2 ? 'bg-amber-100 text-amber-800' : 'bg-slate-100 text-slate-600'
                    }`}>
                      {a.priority && a.priority <= 1 ? '高' : a.priority === 2 ? '中' : '低'}
                    </span>
                    <span className="text-xs text-gray-400">{a.created_at?.slice(0, 16)}</span>
                  </div>
                  {a.priority !== undefined && a.priority <= 1 && (
                    <div className="mt-1.5 h-0.5 rounded bg-red-400" />
                  )}
                </div>
              )) : (
                <div className="px-4 py-12 text-center text-sm text-gray-400">暂无审批项</div>
              )}
            </div>
          </div>

          {/* Detail */}
          <div className="lg:col-span-3 rounded-lg border border-gray-200 bg-white shadow-sm overflow-hidden">
            {selected ? (
              <div className="p-5">
                <div className="flex items-start justify-between mb-4">
                  <div>
                    <h2 className="text-lg font-semibold text-gray-800">{selected.title}</h2>
                    <div className="flex items-center gap-2 mt-2">
                      <StatusBadge status={selected.status} />
                      <span className="text-xs text-gray-400">类型: {selected.type}</span>
                      <span className="text-xs text-gray-400">创建: {selected.created_at?.slice(0, 16)}</span>
                    </div>
                  </div>
                </div>
                {selected.detail && (
                  <div className="rounded-lg bg-gray-50 p-4 text-sm text-gray-700 whitespace-pre-wrap mb-4">
                    {selected.detail}
                  </div>
                )}
                {selected.resolved_at && (
                  <div className="text-xs text-gray-400 mb-4">
                    处理时间: {selected.resolved_at.slice(0, 16)} | 处理人: {selected.resolved_by}
                  </div>
                )}
                {selected.status === 'pending' && (
                  <div className="flex items-center gap-2 pt-4 border-t border-gray-100">
                    <button onClick={() => handleApprove(selected.id)}
                      className="px-4 py-2 text-sm font-medium rounded-md bg-green-600 text-white hover:bg-green-700">
                      通过
                    </button>
                    <button onClick={() => handleReject(selected.id)}
                      className="px-4 py-2 text-sm font-medium rounded-md bg-red-600 text-white hover:bg-red-700">
                      驳回
                    </button>
                  </div>
                )}
              </div>
            ) : (
              <div className="flex items-center justify-center h-full py-20 text-gray-400">
                <div className="text-center">
                  <CheckCircle className="w-12 h-12 mx-auto mb-3 text-gray-300" />
                  <div className="text-sm">选择左侧审批项查看详情</div>
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
