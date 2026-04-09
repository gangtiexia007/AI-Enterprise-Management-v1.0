import { useEffect, useState, useCallback } from 'react';
import { FileText } from 'lucide-react';
import FilterChips from '../components/ui/FilterChips';
import { getAuditLogs, type AuditLogEntry } from '../api/client';

const ACTION_FILTERS = [
  { label: '全部', value: '' },
  { label: '任务', value: 'task' },
  { label: '审批', value: 'approval' },
  { label: '辅导', value: 'coaching' },
  { label: '飞书', value: 'feishu' },
  { label: 'Agent', value: 'agent' },
];

export default function AuditLogs() {
  const [logs, setLogs] = useState<AuditLogEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [filterAction, setFilterAction] = useState('');

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const params: Record<string, string> = { limit: '200' };
      if (filterAction) params.action = filterAction;
      const l = await getAuditLogs(params);
      setLogs(Array.isArray(l) ? l : []);
    } catch { setLogs([]); }
    setLoading(false);
  }, [filterAction]);

  useEffect(() => { load(); }, [load]);

  return (
    <div className="space-y-5">
      <FilterChips label="类型" options={ACTION_FILTERS} value={filterAction} onChange={setFilterAction} />

      {loading ? (
        <div className="text-center py-12 text-gray-400">加载中...</div>
      ) : logs.length === 0 ? (
        <div className="text-center py-16 text-gray-400">
          <FileText className="w-12 h-12 mx-auto mb-3 text-gray-300" />
          <div className="text-sm font-semibold text-gray-600">暂无审计记录</div>
        </div>
      ) : (
        <div className="rounded-lg border border-gray-200 bg-white shadow-sm overflow-hidden">
          <div className="divide-y divide-gray-100">
            {logs.map((log) => (
              <div key={log.id} className="px-4 py-3 hover:bg-gray-50/80 flex items-start gap-4">
                <div className="flex-shrink-0 mt-1">
                  <div className="h-2 w-2 rounded-full bg-brand-400" />
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="text-sm font-medium text-gray-900">{log.actor || 'system'}</span>
                    <span className="text-gray-400">·</span>
                    <span className="text-sm text-gray-700">{log.action}</span>
                    {log.resource_type && (
                      <span className="inline-flex px-1.5 py-0.5 rounded text-[10px] bg-gray-100 text-gray-500">
                        {log.resource_type}{log.resource_id ? ` #${log.resource_id.slice(0, 8)}` : ''}
                      </span>
                    )}
                  </div>
                  {log.detail && (
                    <div className="text-xs text-gray-500 mt-1 truncate">{log.detail}</div>
                  )}
                </div>
                <div className="text-xs text-gray-400 font-mono whitespace-nowrap flex-shrink-0">
                  {log.created_at?.slice(0, 19)}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
