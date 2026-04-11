import { useEffect, useState, useCallback } from 'react';
import { BarChart3, Plus, Trophy, TrendingUp, TrendingDown, Minus } from 'lucide-react';
import StatCard from '../components/ui/StatCard';
import StatusBadge from '../components/ui/StatusBadge';
import FilterChips from '../components/ui/FilterChips';
import Modal from '../components/Modal';
import { getKPIs, getKPISummary, createKPI, deleteKPI, getEmployees, getBitableRecords, type KPIRecord, type KPISummary, type Employee } from '../api/client';

type KpiTab = 'kpi' | 'scoreboard';

const inputCls = "w-full rounded-btn border border-border bg-surface-1 px-3 py-2 text-[13px] text-txt-1 placeholder:text-txt-4 focus:border-accent/40 focus:outline-none transition-colors";

export default function KPI() {
  const [tab, setTab] = useState<KpiTab>('kpi');

  return (
    <div className="space-y-5">
      <div className="flex gap-0 border-b border-border">
        <button onClick={() => setTab('kpi')}
          className={`flex items-center gap-2 px-4 py-3 text-[13px] font-medium border-b-2 transition-colors ${tab === 'kpi' ? 'border-accent text-accent' : 'border-transparent text-txt-4 hover:text-txt-2'}`}>
          <BarChart3 className="w-4 h-4" />KPI 绩效
        </button>
        <button onClick={() => setTab('scoreboard')}
          className={`flex items-center gap-2 px-4 py-3 text-[13px] font-medium border-b-2 transition-colors ${tab === 'scoreboard' ? 'border-accent text-accent' : 'border-transparent text-txt-4 hover:text-txt-2'}`}>
          <Trophy className="w-4 h-4" />运营排行
        </button>
      </div>
      {tab === 'kpi' && <KpiTab />}
      {tab === 'scoreboard' && <ScoreboardTab />}
    </div>
  );
}

function KpiTab() {
  const [records, setRecords] = useState<KPIRecord[]>([]); const [summary, setSummary] = useState<KPISummary[]>([]); const [employees, setEmployees] = useState<Employee[]>([]);
  const [loading, setLoading] = useState(true); const [filterEmployee, setFilterEmployee] = useState(''); const [modalOpen, setModalOpen] = useState(false);
  const [form, setForm] = useState({ employee_id: 0, employee_name: '', metric_name: '', target_value: 0, actual_value: 0, weight: 1.0, period: '' }); const [saving, setSaving] = useState(false);

  const load = useCallback(async () => { setLoading(true); try { const p: Record<string,string> = {}; if (filterEmployee) p.employee_id = filterEmployee; const [r,s,e] = await Promise.all([getKPIs(p), getKPISummary().catch(()=>[]), getEmployees().catch(()=>[])]); setRecords(Array.isArray(r)?r:[]); setSummary(Array.isArray(s)?s:[]); setEmployees(Array.isArray(e)?e:[]); } catch { setRecords([]); } setLoading(false); }, [filterEmployee]);
  useEffect(() => { load(); }, [load]);

  const empFilters = [{ label: '全部', value: '' }, ...employees.map(e => ({ label: e.name, value: String(e.id) }))];
  const avgScore = summary.length > 0 ? Math.round(summary.reduce((s,r) => s + r.avg_score, 0) / summary.length) : 0;
  const grouped = records.reduce<Record<string, KPIRecord[]>>((acc, r) => { const k = r.employee_name || '未知'; if (!acc[k]) acc[k] = []; acc[k].push(r); return acc; }, {});
  const save = async () => { setSaving(true); try { await createKPI(form); setModalOpen(false); load(); } catch (e) { alert(String(e)); } setSaving(false); };
  const handleDelete = async (id: number) => { if (confirm('确认删除？')) { await deleteKPI(id); load(); } };

  return (
    <div className="space-y-5">
      <div className="grid grid-cols-2 lg:grid-cols-3 gap-3">
        <StatCard label="KPI 记录" value={records.length} icon={<BarChart3 className="w-4 h-4" />} />
        <StatCard label="平均分" value={avgScore} accent="text-emerald-700" subtitle="全员平均绩效分" />
        <StatCard label="考核员工" value={summary.length} accent="text-accent" />
      </div>
      <div className="flex items-center justify-between">
        <FilterChips label="员工" options={empFilters} value={filterEmployee} onChange={setFilterEmployee} />
        <button onClick={() => { setForm({ employee_id:0, employee_name:'', metric_name:'', target_value:0, actual_value:0, weight:1.0, period:'' }); setModalOpen(true); }}
          className="flex items-center gap-1.5 px-3 py-1.5 text-[13px] font-medium bg-accent text-white rounded-btn hover:bg-accent-hover transition-colors"><Plus className="w-3.5 h-3.5" /> 新增 KPI</button>
      </div>
      {loading ? <div className="text-center py-12 text-txt-4 text-[13px]">加载中...</div>
        : Object.keys(grouped).length === 0 ? <div className="text-center py-16"><BarChart3 className="w-10 h-10 mx-auto mb-3 text-txt-4" /><div className="text-[14px] font-medium text-txt-3">暂无 KPI 数据</div></div>
        : <div className="space-y-4">{Object.entries(grouped).map(([name, items]) => (
          <div key={name} className="rounded-card border border-border bg-surface-1 overflow-hidden">
            <div className="border-b border-border-subtle px-4 py-2.5 flex items-center justify-between"><h3 className="text-[13px] font-semibold text-txt-1">{name}</h3><span className="text-[11px] text-txt-4">{items.length} 项指标</span></div>
            <table className="min-w-full text-[13px]">
              <thead><tr className="text-left text-[11px] text-txt-4 border-b border-border-subtle">
                <th className="px-4 py-2 font-medium">指标名称</th><th className="px-4 py-2 font-medium">周期</th><th className="px-4 py-2 font-medium text-right">目标</th><th className="px-4 py-2 font-medium text-right">实际</th><th className="px-4 py-2 font-medium text-right">得分</th><th className="px-4 py-2 font-medium">等级</th><th className="px-4 py-2 font-medium text-right">操作</th>
              </tr></thead>
              <tbody className="divide-y divide-border-subtle">{items.map(r => (
                <tr key={r.id} className="hover:bg-surface-3/40 transition-colors">
                  <td className="px-4 py-2.5 font-medium text-txt-1">{r.metric_name}</td>
                  <td className="px-4 py-2.5"><span className="inline-flex px-1.5 py-0.5 rounded-micro text-[11px] bg-gray-100 text-txt-3">{r.period || '-'}</span></td>
                  <td className="px-4 py-2.5 text-right text-txt-3 tabular-nums">{r.target_value}</td>
                  <td className="px-4 py-2.5 text-right text-txt-3 tabular-nums">{r.actual_value}</td>
                  <td className="px-4 py-2.5 text-right font-medium text-txt-1 tabular-nums">{r.score}</td>
                  <td className="px-4 py-2.5"><StatusBadge status={r.grade || '-'} /></td>
                  <td className="px-4 py-2.5 text-right"><button onClick={() => handleDelete(r.id)} className="text-[12px] text-red-400 hover:text-red-600 transition-colors">删除</button></td>
                </tr>
              ))}</tbody>
            </table>
          </div>
        ))}</div>}
      <Modal open={modalOpen} onClose={() => setModalOpen(false)} title="新增 KPI"
        footer={<><button onClick={() => setModalOpen(false)} className="px-3 py-1.5 text-[13px] border border-border rounded-btn text-txt-3 hover:bg-surface-3 transition-colors">取消</button>
          <button onClick={save} disabled={saving || !form.metric_name || !form.employee_id} className="px-3 py-1.5 text-[13px] bg-accent text-white rounded-btn hover:bg-accent-hover disabled:opacity-40 transition-colors">{saving ? '保存中...' : '创建'}</button></>}>
        <div className="space-y-4">
          <div><label className="block text-[12px] font-medium text-txt-3 mb-1.5">员工 <span className="text-red-500">*</span></label><select value={form.employee_id} onChange={e => { const emp = employees.find(x=>x.id===Number(e.target.value)); setForm({...form, employee_id: Number(e.target.value), employee_name: emp?.name || ''}); }} className={inputCls}><option value={0}>选择员工</option>{employees.map(e => <option key={e.id} value={e.id}>{e.name}</option>)}</select></div>
          <div><label className="block text-[12px] font-medium text-txt-3 mb-1.5">指标名称 <span className="text-red-500">*</span></label><input value={form.metric_name} onChange={e => setForm({...form, metric_name: e.target.value})} className={inputCls} /></div>
          <div className="grid grid-cols-2 gap-3"><div><label className="block text-[12px] font-medium text-txt-3 mb-1.5">考核周期</label><input value={form.period} onChange={e => setForm({...form, period: e.target.value})} placeholder="2024-Q1" className={inputCls} /></div><div><label className="block text-[12px] font-medium text-txt-3 mb-1.5">权重</label><input type="number" step="0.1" value={form.weight} onChange={e => setForm({...form, weight: Number(e.target.value)})} className={inputCls} /></div></div>
          <div className="grid grid-cols-2 gap-3"><div><label className="block text-[12px] font-medium text-txt-3 mb-1.5">目标值</label><input type="number" value={form.target_value} onChange={e => setForm({...form, target_value: Number(e.target.value)})} className={inputCls} /></div><div><label className="block text-[12px] font-medium text-txt-3 mb-1.5">实际值</label><input type="number" value={form.actual_value} onChange={e => setForm({...form, actual_value: Number(e.target.value)})} className={inputCls} /></div></div>
        </div>
      </Modal>
    </div>
  );
}

interface OperatorRow {
  name: string;
  effective_links: number;
  hit_count: number;
  hit_rate: number;
  trend: 'up' | 'down' | 'flat';
}

const PLACEHOLDER_DATA: OperatorRow[] = [
  { name: '运营 A', effective_links: 120, hit_count: 18, hit_rate: 15.0, trend: 'up' },
  { name: '运营 B', effective_links: 95, hit_count: 12, hit_rate: 12.6, trend: 'up' },
  { name: '运营 C', effective_links: 88, hit_count: 8, hit_rate: 9.1, trend: 'flat' },
  { name: '运营 D', effective_links: 76, hit_count: 5, hit_rate: 6.6, trend: 'down' },
  { name: '运营 E', effective_links: 60, hit_count: 3, hit_rate: 5.0, trend: 'down' },
];

const TrendIcon = ({ trend }: { trend: string }) => {
  if (trend === 'up') return <TrendingUp className="w-3.5 h-3.5 text-emerald-600" />;
  if (trend === 'down') return <TrendingDown className="w-3.5 h-3.5 text-red-500" />;
  return <Minus className="w-3.5 h-3.5 text-txt-4" />;
};

const PERIOD_OPTIONS = [
  { label: '本周', value: 'week' },
  { label: '本月', value: 'month' },
];

function ScoreboardTab() {
  const [period, setPeriod] = useState('week');
  const [operators, setOperators] = useState<OperatorRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [isPlaceholder, setIsPlaceholder] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const res = await getBitableRecords('operator_scoreboard', { page_size: 50 });
      if (res?.items && res.items.length > 0) {
        const rows: OperatorRow[] = res.items.map(rec => {
          const f = rec.fields || {};
          const links = Number(f['effective_links'] ?? f['有效链接数'] ?? 0);
          const hits = Number(f['hit_count'] ?? f['命中数'] ?? 0);
          return {
            name: String(f['name'] ?? f['姓名'] ?? f['运营'] ?? ''),
            effective_links: links,
            hit_count: hits,
            hit_rate: links > 0 ? Math.round((hits / links) * 1000) / 10 : 0,
            trend: (f['trend'] ?? 'flat') as 'up' | 'down' | 'flat',
          };
        }).filter(r => r.name).sort((a, b) => b.hit_rate - a.hit_rate);
        setOperators(rows);
        setIsPlaceholder(false);
      } else {
        setOperators(PLACEHOLDER_DATA);
        setIsPlaceholder(true);
      }
    } catch {
      setOperators(PLACEHOLDER_DATA);
      setIsPlaceholder(true);
    }
    setLoading(false);
  }, []);

  useEffect(() => { load(); }, [load]);

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between">
        <FilterChips label="周期" options={PERIOD_OPTIONS} value={period} onChange={setPeriod} />
        {isPlaceholder && (
          <span className="text-[11px] text-amber-600 bg-amber-50 px-2 py-1 rounded-micro">
            暂无实际数据，显示为示例
          </span>
        )}
      </div>

      {operators.length >= 3 && (
        <div className="grid grid-cols-3 gap-3">
          {operators.slice(0, 3).map((op, i) => {
            const medals = ['bg-amber-50 border-amber-200 text-amber-700', 'bg-gray-50 border-gray-200 text-gray-600', 'bg-orange-50 border-orange-200 text-orange-700'];
            const ranks = ['1st', '2nd', '3rd'];
            return (
              <div key={op.name} className={`rounded-card border p-4 ${medals[i]}`}>
                <div className="flex items-start justify-between">
                  <div>
                    <div className="flex items-center gap-2">
                      <Trophy className="w-4 h-4" />
                      <span className="text-[14px] font-bold">{ranks[i]}</span>
                    </div>
                    <div className="text-[15px] font-semibold mt-2">{op.name}</div>
                  </div>
                  <TrendIcon trend={op.trend} />
                </div>
                <div className="mt-3 grid grid-cols-3 gap-2 text-center">
                  <div>
                    <div className="text-[11px] opacity-70">有效链接</div>
                    <div className="text-[14px] font-bold">{op.effective_links}</div>
                  </div>
                  <div>
                    <div className="text-[11px] opacity-70">命中数</div>
                    <div className="text-[14px] font-bold">{op.hit_count}</div>
                  </div>
                  <div>
                    <div className="text-[11px] opacity-70">命中率</div>
                    <div className="text-[14px] font-bold">{op.hit_rate}%</div>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {loading ? (
        <div className="text-center py-12 text-txt-4 text-[13px]">加载中...</div>
      ) : (
        <div className="rounded-card border border-border bg-surface-1 overflow-hidden">
          <div className="border-b border-border-subtle px-4 py-3">
            <h3 className="text-[13px] font-semibold text-txt-1">运营排行榜</h3>
          </div>
          <table className="min-w-full text-[13px]">
            <thead>
              <tr className="border-b border-border text-left text-[11px] font-medium text-txt-4 uppercase tracking-wider bg-surface-0/60">
                <th className="px-4 py-3 w-12">排名</th>
                <th className="px-4 py-3">运营</th>
                <th className="px-4 py-3 text-right">有效链接数</th>
                <th className="px-4 py-3 text-right">命中数</th>
                <th className="px-4 py-3 text-right">命中率</th>
                <th className="px-4 py-3 text-center">趋势</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border-subtle">
              {operators.map((op, i) => (
                <tr key={op.name} className={`transition-colors ${i < 3 ? 'bg-accent-soft/30' : 'hover:bg-surface-3/40'}`}>
                  <td className="px-4 py-3">
                    <span className={`inline-flex items-center justify-center h-6 w-6 rounded-full text-[11px] font-bold ${
                      i === 0 ? 'bg-amber-100 text-amber-700' :
                      i === 1 ? 'bg-gray-100 text-gray-600' :
                      i === 2 ? 'bg-orange-100 text-orange-700' :
                      'bg-surface-3 text-txt-3'
                    }`}>{i + 1}</span>
                  </td>
                  <td className="px-4 py-3 font-medium text-txt-1">{op.name}</td>
                  <td className="px-4 py-3 text-right text-txt-3">{op.effective_links}</td>
                  <td className="px-4 py-3 text-right text-txt-3">{op.hit_count}</td>
                  <td className="px-4 py-3 text-right">
                    <span className={`font-medium ${op.hit_rate >= 10 ? 'text-emerald-700' : op.hit_rate >= 5 ? 'text-amber-700' : 'text-red-600'}`}>
                      {op.hit_rate}%
                    </span>
                  </td>
                  <td className="px-4 py-3 text-center"><TrendIcon trend={op.trend} /></td>
                </tr>
              ))}
              {operators.length === 0 && (
                <tr><td colSpan={6} className="px-4 py-12 text-center text-txt-4 text-[13px]">暂无排行数据</td></tr>
              )}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
