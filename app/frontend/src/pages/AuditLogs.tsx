import { useEffect, useState, useCallback } from 'react';
import { FileText } from 'lucide-react';
import FilterChips from '../components/ui/FilterChips';
import { getAuditLogs, type AuditLogEntry } from '../api/client';

const ACTION_FILTERS = [{ label: '全部', value: '' }, { label: '任务', value: 'task' }, { label: '审批', value: 'approval' }, { label: '辅导', value: 'coaching' }, { label: '飞书', value: 'feishu' }, { label: 'Agent', value: 'agent' }];

export default function AuditLogs() {
  const [logs, setLogs] = useState<AuditLogEntry[]>([]); const [loading, setLoading] = useState(true); const [filterAction, setFilterAction] = useState('');
  const load = useCallback(async () => { setLoading(true); try { const p: Record<string,string> = { limit: '200' }; if (filterAction) p.action = filterAction; const l = await getAuditLogs(p); setLogs(Array.isArray(l)?l:[]); } catch { setLogs([]); } setLoading(false); }, [filterAction]);
  useEffect(() => { load(); }, [load]);

  return (
    <div className="space-y-5">
      <FilterChips label="类型" options={ACTION_FILTERS} value={filterAction} onChange={setFilterAction} />
      {loading ? <div className="text-center py-12 text-txt-4 text-[13px]">加载中...</div>
        : logs.length === 0 ? <div className="text-center py-16"><FileText className="w-10 h-10 mx-auto mb-3 text-txt-4" /><div className="text-[14px] font-medium text-txt-3">暂无审计记录</div></div>
        : <div className="rounded-card border border-border bg-surface-1 overflow-hidden"><div className="divide-y divide-border-subtle">
          {logs.map(log => (
            <div key={log.id} className="px-4 py-3 hover:bg-surface-3/40 transition-colors flex items-start gap-4">
              <div className="flex-shrink-0 mt-1.5"><div className="h-1.5 w-1.5 rounded-full bg-accent" /></div>
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="text-[13px] font-medium text-txt-1">{log.actor || 'system'}</span><span className="text-txt-4">·</span><span className="text-[13px] text-txt-3">{log.action}</span>
                  {log.resource_type && <span className="inline-flex px-1.5 py-0.5 rounded-micro text-[10px] bg-gray-100 text-txt-4">{log.resource_type}{log.resource_id ? ` #${log.resource_id.slice(0, 8)}` : ''}</span>}
                </div>
                {log.detail && <div className="text-[12px] text-txt-4 mt-1 truncate">{log.detail}</div>}
              </div>
              <div className="text-[11px] text-txt-4 font-mono whitespace-nowrap flex-shrink-0">{log.created_at?.slice(0, 19)}</div>
            </div>
          ))}
        </div></div>}
    </div>
  );
}
