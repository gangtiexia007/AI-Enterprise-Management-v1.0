import { useState, useEffect, useCallback, useRef } from 'react';
import { Upload, Trophy, BarChart3, Layers } from 'lucide-react';
import { podStats, podOperatorKpi, podNicheStats, uploadPodOrders, uploadPodProducts } from '../api/client';

type Tab = 'upload' | 'ranking' | 'niche';

export default function PodPerformance() {
  const [tab, setTab] = useState<Tab>('upload');

  return (
    <div className="space-y-5">
      <div className="flex gap-0 border-b border-border">
        <button onClick={() => setTab('upload')}
          className={`flex items-center gap-2 px-4 py-3 text-[13px] font-medium border-b-2 transition-colors ${tab === 'upload' ? 'border-accent text-accent' : 'border-transparent text-txt-4 hover:text-txt-2'}`}>
          <Upload className="w-4 h-4" />数据上传
        </button>
        <button onClick={() => setTab('ranking')}
          className={`flex items-center gap-2 px-4 py-3 text-[13px] font-medium border-b-2 transition-colors ${tab === 'ranking' ? 'border-accent text-accent' : 'border-transparent text-txt-4 hover:text-txt-2'}`}>
          <Trophy className="w-4 h-4" />运营排名
        </button>
        <button onClick={() => setTab('niche')}
          className={`flex items-center gap-2 px-4 py-3 text-[13px] font-medium border-b-2 transition-colors ${tab === 'niche' ? 'border-accent text-accent' : 'border-transparent text-txt-4 hover:text-txt-2'}`}>
          <Layers className="w-4 h-4" />赛道概览
        </button>
      </div>
      {tab === 'upload' && <UploadTab />}
      {tab === 'ranking' && <RankingTab />}
      {tab === 'niche' && <NicheTab />}
    </div>
  );
}

/* ========== Tab 1: 数据上传 ========== */

interface PodStatsData {
  total_orders?: number;
  total_products?: number;
  total_operators?: number;
  total_niches?: number;
  total_revenue_cny?: number;
}

function UploadTab() {
  const [orderUploading, setOrderUploading] = useState(false);
  const [productUploading, setProductUploading] = useState(false);
  const [orderResult, setOrderResult] = useState<string | null>(null);
  const [productResult, setProductResult] = useState<string | null>(null);
  const [orderError, setOrderError] = useState<string | null>(null);
  const [productError, setProductError] = useState<string | null>(null);
  const [stats, setStats] = useState<PodStatsData | null>(null);
  const orderRef = useRef<HTMLInputElement>(null);
  const productRef = useRef<HTMLInputElement>(null);

  const loadStats = useCallback(async () => {
    try {
      const s = await podStats();
      setStats(s as PodStatsData);
    } catch {
      setStats(null);
    }
  }, []);

  useEffect(() => { loadStats(); }, [loadStats]);

  const handleOrderUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setOrderUploading(true);
    setOrderResult(null);
    setOrderError(null);
    try {
      const res = await uploadPodOrders(file);
      setOrderResult(`导入 ${res.imported ?? 0} 条，跳过 ${res.skipped ?? 0} 条`);
      loadStats();
    } catch (err) {
      setOrderError(String(err));
    }
    setOrderUploading(false);
    if (orderRef.current) orderRef.current.value = '';
  };

  const handleProductUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setProductUploading(true);
    setProductResult(null);
    setProductError(null);
    try {
      const res = await uploadPodProducts(file);
      setProductResult(`导入 ${res.imported ?? 0} 条，跳过 ${res.skipped ?? 0} 条`);
      loadStats();
    } catch (err) {
      setProductError(String(err));
    }
    setProductUploading(false);
    if (productRef.current) productRef.current.value = '';
  };

  return (
    <div className="space-y-5">
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="rounded-card border-2 border-dashed border-border-mid p-8 text-center">
          <Upload className="w-8 h-8 mx-auto mb-3 text-txt-4" />
          <div className="text-[14px] font-medium text-txt-1 mb-1">上传订单 Excel</div>
          <div className="text-[12px] text-txt-4 mb-4">支持 .xlsx / .xls 格式的订单数据</div>
          <label className="inline-flex items-center gap-2 px-4 py-2 text-[13px] font-medium bg-accent text-white rounded-btn hover:bg-accent-hover cursor-pointer transition-colors">
            {orderUploading ? '上传中…' : '选择文件'}
            <input ref={orderRef} type="file" accept=".xlsx,.xls" onChange={handleOrderUpload} className="hidden" disabled={orderUploading} />
          </label>
          {orderResult && <div className="mt-3 text-[12px] text-emerald-700 bg-emerald-50 px-3 py-1.5 rounded-btn">{orderResult}</div>}
          {orderError && <div className="mt-3 text-[12px] text-red-700 bg-red-50 px-3 py-1.5 rounded-btn">{orderError}</div>}
        </div>

        <div className="rounded-card border-2 border-dashed border-border-mid p-8 text-center">
          <Upload className="w-8 h-8 mx-auto mb-3 text-txt-4" />
          <div className="text-[14px] font-medium text-txt-1 mb-1">上传产品 Excel</div>
          <div className="text-[12px] text-txt-4 mb-4">支持 .xlsx / .xls 格式的产品数据</div>
          <label className="inline-flex items-center gap-2 px-4 py-2 text-[13px] font-medium bg-accent text-white rounded-btn hover:bg-accent-hover cursor-pointer transition-colors">
            {productUploading ? '上传中…' : '选择文件'}
            <input ref={productRef} type="file" accept=".xlsx,.xls" onChange={handleProductUpload} className="hidden" disabled={productUploading} />
          </label>
          {productResult && <div className="mt-3 text-[12px] text-emerald-700 bg-emerald-50 px-3 py-1.5 rounded-btn">{productResult}</div>}
          {productError && <div className="mt-3 text-[12px] text-red-700 bg-red-50 px-3 py-1.5 rounded-btn">{productError}</div>}
        </div>
      </div>

      {stats && (
        <div>
          <h3 className="text-[13px] font-semibold text-txt-1 mb-3">基础统计</h3>
          <div className="grid grid-cols-2 lg:grid-cols-5 gap-3">
            <StatTile label="总订单数" value={stats.total_orders ?? 0} />
            <StatTile label="总产品数" value={stats.total_products ?? 0} />
            <StatTile label="运营人数" value={stats.total_operators ?? 0} />
            <StatTile label="赛道数" value={stats.total_niches ?? 0} />
            <StatTile label="总销售额(CNY)" value={`¥${(stats.total_revenue_cny ?? 0).toLocaleString()}`} />
          </div>
        </div>
      )}
    </div>
  );
}

function StatTile({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="rounded-card border border-border bg-surface-1 p-4">
      <div className="text-[11px] text-txt-4 font-medium">{label}</div>
      <div className="text-[24px] font-bold text-accent mt-1 tabular-nums">{value}</div>
    </div>
  );
}

/* ========== Tab 2: 运营排名 ========== */

interface OperatorKpiRow {
  operator_name: string;
  effective_links: number;
  s_grade_count: number;
  total_orders: number;
  revenue_cny: number;
  cancel_rate: number;
  hit_rate: number;
}

function getWeekRange(): { start: string; end: string } {
  const now = new Date();
  const day = now.getDay() || 7;
  const mon = new Date(now);
  mon.setDate(now.getDate() - day + 1);
  const sun = new Date(mon);
  sun.setDate(mon.getDate() + 6);
  return { start: fmt(mon), end: fmt(sun) };
}

function getMonthRange(): { start: string; end: string } {
  const now = new Date();
  const start = new Date(now.getFullYear(), now.getMonth(), 1);
  const end = new Date(now.getFullYear(), now.getMonth() + 1, 0);
  return { start: fmt(start), end: fmt(end) };
}

function fmt(d: Date) {
  return d.toISOString().slice(0, 10);
}

function RankingTab() {
  const [period, setPeriod] = useState<'week' | 'month'>('week');
  const [rows, setRows] = useState<OperatorKpiRow[]>([]);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const range = period === 'week' ? getWeekRange() : getMonthRange();
      const res = await podOperatorKpi({ period_start: range.start, period_end: range.end });
      const data = Array.isArray(res) ? res : [];
      data.sort((a: OperatorKpiRow, b: OperatorKpiRow) => b.effective_links - a.effective_links);
      setRows(data);
    } catch {
      setRows([]);
    }
    setLoading(false);
  }, [period]);

  useEffect(() => { load(); }, [load]);

  return (
    <div className="space-y-5">
      <div className="flex items-center gap-2">
        <span className="text-[12px] text-txt-4 font-medium mr-1">周期</span>
        {(['week', 'month'] as const).map(p => (
          <button key={p} onClick={() => setPeriod(p)}
            className={`px-3 py-1.5 text-[12px] font-medium rounded-btn transition-colors ${period === p ? 'bg-accent text-white' : 'bg-surface-3 text-txt-3 hover:bg-border'}`}>
            {p === 'week' ? '本周' : '本月'}
          </button>
        ))}
      </div>

      {loading ? (
        <div className="text-center py-12 text-txt-4 text-[13px]">加载中...</div>
      ) : (
        <div className="rounded-card border border-border bg-surface-1 overflow-hidden">
          <div className="border-b border-border-subtle px-4 py-3">
            <h3 className="text-[13px] font-semibold text-txt-1">运营 KPI 排名</h3>
          </div>
          <div className="overflow-x-auto">
            <table className="min-w-full text-[13px]">
              <thead>
                <tr className="border-b border-border text-left text-[11px] font-medium text-txt-4 uppercase tracking-wider bg-surface-0/60">
                  <th className="px-4 py-3 w-12">排名</th>
                  <th className="px-4 py-3">运营</th>
                  <th className="px-4 py-3 text-right">有效链接数</th>
                  <th className="px-4 py-3 text-right">S级爆款</th>
                  <th className="px-4 py-3 text-right">总出单量</th>
                  <th className="px-4 py-3 text-right">销售额(CNY)</th>
                  <th className="px-4 py-3 text-right">取消率</th>
                  <th className="px-4 py-3 text-right">选品命中率</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border-subtle">
                {rows.map((r, i) => (
                  <tr key={r.operator_name} className={`transition-colors ${i < 3 ? 'bg-accent-soft/30' : 'hover:bg-surface-3/40'}`}>
                    <td className="px-4 py-3">
                      <span className={`inline-flex items-center justify-center h-6 w-6 rounded-full text-[11px] font-bold ${
                        i === 0 ? 'bg-amber-100 text-amber-700' :
                        i === 1 ? 'bg-gray-100 text-gray-600' :
                        i === 2 ? 'bg-orange-100 text-orange-700' :
                        'bg-surface-3 text-txt-3'
                      }`}>{i + 1}</span>
                    </td>
                    <td className="px-4 py-3 font-medium text-txt-1">{r.operator_name}</td>
                    <td className="px-4 py-3 text-right tabular-nums text-txt-3">{r.effective_links}</td>
                    <td className="px-4 py-3 text-right tabular-nums">
                      <span className={r.s_grade_count > 5 ? 'text-emerald-700 font-medium' : 'text-txt-3'}>{r.s_grade_count}</span>
                    </td>
                    <td className="px-4 py-3 text-right tabular-nums text-txt-3">{r.total_orders.toLocaleString()}</td>
                    <td className="px-4 py-3 text-right tabular-nums text-txt-3">¥{r.revenue_cny.toLocaleString()}</td>
                    <td className="px-4 py-3 text-right tabular-nums">
                      <span className={r.cancel_rate > 10 ? 'text-red-600 font-medium' : 'text-txt-3'}>{r.cancel_rate.toFixed(1)}%</span>
                    </td>
                    <td className="px-4 py-3 text-right tabular-nums text-txt-3">{r.hit_rate.toFixed(1)}%</td>
                  </tr>
                ))}
                {rows.length === 0 && (
                  <tr><td colSpan={8} className="px-4 py-12 text-center text-txt-4 text-[13px]">暂无排名数据</td></tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}

/* ========== Tab 3: 赛道概览 ========== */

interface NicheRow {
  niche: string;
  total_orders: number;
  sku_count: number;
  operators: string[];
}

function NicheTab() {
  const [rows, setRows] = useState<NicheRow[]>([]);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const res = await podNicheStats();
      const data = Array.isArray(res) ? res : [];
      data.sort((a: NicheRow, b: NicheRow) => b.total_orders - a.total_orders);
      setRows(data);
    } catch {
      setRows([]);
    }
    setLoading(false);
  }, []);

  useEffect(() => { load(); }, [load]);

  return (
    <div className="space-y-5">
      {loading ? (
        <div className="text-center py-12 text-txt-4 text-[13px]">加载中...</div>
      ) : rows.length === 0 ? (
        <div className="text-center py-16">
          <Layers className="w-10 h-10 mx-auto mb-3 text-txt-4" />
          <div className="text-[14px] font-medium text-txt-3">暂无赛道数据</div>
        </div>
      ) : (
        <div className="rounded-card border border-border bg-surface-1 overflow-hidden">
          <div className="border-b border-border-subtle px-4 py-3">
            <h3 className="text-[13px] font-semibold text-txt-1">赛道概览</h3>
          </div>
          <div className="overflow-x-auto">
            <table className="min-w-full text-[13px]">
              <thead>
                <tr className="border-b border-border text-left text-[11px] font-medium text-txt-4 uppercase tracking-wider bg-surface-0/60">
                  <th className="px-4 py-3 w-12">#</th>
                  <th className="px-4 py-3">赛道</th>
                  <th className="px-4 py-3 text-right">出单量</th>
                  <th className="px-4 py-3 text-right">SKU 数</th>
                  <th className="px-4 py-3">运营分布</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border-subtle">
                {rows.map((r, i) => (
                  <tr key={r.niche} className="hover:bg-surface-3/40 transition-colors">
                    <td className="px-4 py-3 text-txt-4 tabular-nums">{i + 1}</td>
                    <td className="px-4 py-3 font-medium text-txt-1">{r.niche}</td>
                    <td className="px-4 py-3 text-right tabular-nums text-txt-3">{r.total_orders.toLocaleString()}</td>
                    <td className="px-4 py-3 text-right tabular-nums text-txt-3">{r.sku_count}</td>
                    <td className="px-4 py-3">
                      <div className="flex flex-wrap gap-1">
                        {(r.operators || []).map(op => (
                          <span key={op} className="inline-flex px-1.5 py-0.5 rounded-micro text-[11px] bg-accent-soft text-accent font-medium">{op}</span>
                        ))}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
