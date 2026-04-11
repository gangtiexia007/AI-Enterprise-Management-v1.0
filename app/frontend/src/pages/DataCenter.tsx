import { useCallback, useEffect, useRef, useState } from 'react';
import { Database, RefreshCw, Search, CalendarPlus, Upload } from 'lucide-react';
import Modal from '../components/Modal';
import {
  getBitableOverview,
  syncBitableAll,
  syncBitableAlias,
  getBitableRecords,
  testBitableConnection,
  generateDailyRows,
  importDailyOpsCsv,
  type BitableTableOverview,
  type BitableRecordRow,
} from '../api/client';

function categoryStyle(cat: string) {
  if (cat === 'A') return 'border-l-blue-500 bg-blue-50/50';
  if (cat === 'B') return 'border-l-emerald-500 bg-emerald-50/50';
  return 'border-l-amber-500 bg-amber-50/50';
}

function categoryLabel(cat: string) {
  if (cat === 'A') return '参考数据';
  if (cat === 'B') return '业务数据';
  return '管理数据';
}

export default function DataCenter() {
  const [overview, setOverview] = useState<BitableTableOverview[]>([]);
  const [loading, setLoading] = useState(true);
  const [syncing, setSyncing] = useState(false);
  const [connOk, setConnOk] = useState<boolean | null>(null);
  const [detailAlias, setDetailAlias] = useState<string | null>(null);
  const [records, setRecords] = useState<BitableRecordRow[]>([]);
  const [pageToken, setPageToken] = useState<string | undefined>();
  const [recLoading, setRecLoading] = useState(false);
  const [searchQ, setSearchQ] = useState('');
  const [lastGlobalSync, setLastGlobalSync] = useState<string | null>(null);
  const [generating, setGenerating] = useState(false);
  const [genResult, setGenResult] = useState<string | null>(null);
  const [importing, setImporting] = useState(false);
  const [importResult, setImportResult] = useState<string | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  const loadOverview = useCallback(async () => {
    setLoading(true);
    try {
      const o = await getBitableOverview();
      setOverview(o);
      const times = o.map((x) => x.last_sync_at).filter(Boolean) as string[];
      if (times.length) {
        const latest = times.sort().slice(-1)[0];
        setLastGlobalSync(latest);
      }
    } catch {
      setOverview([]);
    }
    setLoading(false);
  }, []);

  useEffect(() => {
    loadOverview();
    testBitableConnection()
      .then(() => setConnOk(true))
      .catch(() => setConnOk(false));
  }, [loadOverview]);

  const openDetail = async (alias: string) => {
    setDetailAlias(alias);
    setRecords([]);
    setPageToken(undefined);
    setSearchQ('');
    setRecLoading(true);
    try {
      const data = await getBitableRecords(alias, { page_size: 30 });
      setRecords(data.items || []);
      setPageToken(data.page_token);
    } catch {
      setRecords([]);
    }
    setRecLoading(false);
  };

  const loadMore = async () => {
    if (!detailAlias || !pageToken) return;
    setRecLoading(true);
    try {
      const data = await getBitableRecords(detailAlias, { page_token: pageToken, page_size: 30, q: searchQ || undefined });
      setRecords((prev) => [...prev, ...(data.items || [])]);
      setPageToken(data.page_token);
    } catch {}
    setRecLoading(false);
  };

  const applySearch = async () => {
    if (!detailAlias) return;
    setRecLoading(true);
    try {
      const data = await getBitableRecords(detailAlias, { page_size: 50, q: searchQ || undefined });
      setRecords(data.items || []);
      setPageToken(data.page_token);
    } catch {
      setRecords([]);
    }
    setRecLoading(false);
  };

  const handleSyncAll = async () => {
    setSyncing(true);
    try {
      await syncBitableAll();
      setLastGlobalSync(new Date().toISOString());
      await loadOverview();
    } catch (e) {
      alert(String(e));
    }
    setSyncing(false);
  };

  const handleSyncOne = async (alias: string) => {
    try {
      await syncBitableAlias(alias);
      await loadOverview();
    } catch (e) {
      alert(String(e));
    }
  };

  const handleGenerate = async () => {
    setGenerating(true);
    setGenResult(null);
    try {
      const today = new Date().toISOString().slice(0, 10);
      const res = await generateDailyRows(today);
      setGenResult(res.message || `已生成 ${res.created} 行`);
      loadOverview();
    } catch (e) { setGenResult(`失败: ${e}`); }
    setGenerating(false);
  };

  const handleCsvUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setImporting(true);
    setImportResult(null);
    try {
      const res = await importDailyOpsCsv(file);
      setImportResult(res.message || `导入 ${res.imported} 行`);
      if (res.error) setImportResult(prev => `${prev} (${res.error})`);
      loadOverview();
    } catch (err) { setImportResult(`失败: ${err}`); }
    setImporting(false);
    if (fileRef.current) fileRef.current.value = '';
  };

  return (
    <div className="space-y-5">
      {/* Daily ops tools */}
      <div className="rounded-card border border-border bg-surface-1 p-4">
        <h3 className="text-[13px] font-semibold text-txt-1 mb-3">每日运营数据 · 快捷工具</h3>
        <div className="flex flex-wrap items-center gap-3">
          <button
            type="button"
            onClick={handleGenerate}
            disabled={generating}
            className="inline-flex items-center gap-2 px-4 py-2 text-[13px] font-medium bg-accent text-white rounded-btn hover:bg-accent-hover disabled:opacity-50 transition-colors"
          >
            <CalendarPlus className={`w-4 h-4 ${generating ? 'animate-pulse' : ''}`} />
            {generating ? '生成中…' : '一键生成今日空行'}
          </button>
          <label className="inline-flex items-center gap-2 px-4 py-2 text-[13px] font-medium border border-border rounded-btn hover:bg-surface-3 cursor-pointer transition-colors">
            <Upload className="w-4 h-4" />
            {importing ? '导入中…' : '导入 CSV'}
            <input ref={fileRef} type="file" accept=".csv,.tsv,.txt" onChange={handleCsvUpload} className="hidden" />
          </label>
          <span className="text-[12px] text-txt-4">支持从 TikTok / Shopee / Temu 后台导出的 CSV</span>
        </div>
        {genResult && <div className="mt-2 text-[12px] text-emerald-700 bg-emerald-50 px-3 py-1.5 rounded-btn">{genResult}</div>}
        {importResult && <div className="mt-2 text-[12px] text-blue-700 bg-blue-50 px-3 py-1.5 rounded-btn">{importResult}</div>}
      </div>

      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <div
            className={`flex items-center gap-2 rounded-btn border border-border px-3 py-1.5 text-[12px] ${
              connOk === true ? 'text-emerald-700 bg-emerald-50' : connOk === false ? 'text-red-700 bg-red-50' : 'text-txt-4 bg-surface-2'
            }`}
          >
            <span className={`w-2 h-2 rounded-full ${connOk === true ? 'bg-emerald-500' : connOk === false ? 'bg-red-500' : 'bg-zinc-300'}`} />
            {connOk === true ? '多维表格已连接' : connOk === false ? '连接失败或未配置' : '检测连接中…'}
          </div>
          {lastGlobalSync && (
            <span className="text-[12px] text-txt-4">最近同步: {new Date(lastGlobalSync).toLocaleString()}</span>
          )}
        </div>
        <button
          type="button"
          onClick={handleSyncAll}
          disabled={syncing}
          className="inline-flex items-center gap-2 px-4 py-2 text-[13px] font-medium bg-accent text-white rounded-btn hover:bg-accent-hover disabled:opacity-50 transition-colors"
        >
          <RefreshCw className={`w-4 h-4 ${syncing ? 'animate-spin' : ''}`} />
          同步全部缓存
        </button>
      </div>

      {loading ? (
        <div className="text-center py-16 text-txt-4 text-[13px]">加载中...</div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-3">
          {overview.map((row) => (
            <div
              key={row.alias}
              className={`rounded-card border border-border border-l-4 p-4 shadow-sm ${categoryStyle(row.category)}`}
            >
              <div className="flex items-start justify-between gap-2">
                <div>
                  <div className="text-[11px] uppercase tracking-wide text-txt-4 font-medium">{categoryLabel(row.category)}</div>
                  <div className="text-[14px] font-semibold text-txt-1 mt-0.5 flex items-center gap-1.5">
                    <Database className="w-4 h-4 text-txt-3 flex-shrink-0" />
                    {row.alias}
                  </div>
                </div>
              </div>
              <div className="mt-3 text-[12px] text-txt-3 space-y-1">
                <div>记录数（估算）: <span className="text-txt-1 font-medium">{row.record_count}</span></div>
                <div className="truncate" title={row.table_id || ''}>
                  table_id: {row.table_id || <span className="text-amber-600">未映射</span>}
                </div>
                {row.last_sync_at && (
                  <div className="text-txt-4">同步: {new Date(row.last_sync_at).toLocaleString()}</div>
                )}
              </div>
              <div className="mt-3 flex gap-2">
                <button
                  type="button"
                  onClick={() => openDetail(row.alias)}
                  disabled={!row.table_id}
                  className="flex-1 px-2 py-1.5 text-[12px] rounded-btn border border-border hover:bg-surface-3 disabled:opacity-40 transition-colors"
                >
                  查看详情
                </button>
                <button
                  type="button"
                  onClick={() => handleSyncOne(row.alias)}
                  disabled={!row.table_id}
                  className="px-2 py-1.5 text-[12px] rounded-btn border border-border hover:bg-surface-3 disabled:opacity-40 transition-colors"
                  title="刷新该表缓存"
                >
                  <RefreshCw className="w-3.5 h-3.5" />
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      <Modal
        open={!!detailAlias}
        onClose={() => setDetailAlias(null)}
        title={detailAlias ? `记录 · ${detailAlias}` : ''}
        width="max-w-3xl"
      >
        <div className="flex gap-2 mb-3">
          <div className="relative flex-1">
            <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-txt-4" />
            <input
              value={searchQ}
              onChange={(e) => setSearchQ(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && applySearch()}
              placeholder="关键词筛选（当前页拉取后本地/服务端过滤）"
              className="w-full rounded-btn border border-border bg-surface-1 pl-8 pr-3 py-2 text-[13px] text-txt-1"
            />
          </div>
          <button type="button" onClick={applySearch} className="px-3 py-2 text-[13px] border border-border rounded-btn hover:bg-surface-3">
            筛选
          </button>
        </div>
        {recLoading && !records.length ? (
          <div className="text-txt-4 text-[13px] py-8 text-center">加载中...</div>
        ) : (
          <div className="space-y-2 max-h-[60vh] overflow-y-auto scrollbar-thin">
            {records.map((r, i) => (
              <div key={r.record_id || `row-${i}`} className="rounded-btn border border-border-subtle p-3 text-[12px] bg-surface-0">
                <div className="text-txt-4 mb-1 font-mono">{r.record_id}</div>
                <pre className="whitespace-pre-wrap break-all text-txt-2">{JSON.stringify(r.fields, null, 2)}</pre>
              </div>
            ))}
            {!records.length && <div className="text-txt-4 text-[13px] text-center py-6">暂无记录或表未映射</div>}
          </div>
        )}
        {pageToken && (
          <div className="mt-3 flex justify-center">
            <button
              type="button"
              onClick={loadMore}
              disabled={recLoading}
              className="px-4 py-2 text-[13px] border border-border rounded-btn hover:bg-surface-3 disabled:opacity-50"
            >
              {recLoading ? '加载中…' : '加载更多'}
            </button>
          </div>
        )}
      </Modal>
    </div>
  );
}
