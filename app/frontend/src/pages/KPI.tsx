import { useEffect, useState, useCallback } from 'react';
import { BarChart3, Plus } from 'lucide-react';
import StatCard from '../components/ui/StatCard';
import StatusBadge from '../components/ui/StatusBadge';
import FilterChips from '../components/ui/FilterChips';
import Modal from '../components/Modal';
import { getKPIs, getKPISummary, createKPI, deleteKPI, getEmployees, type KPIRecord, type KPISummary, type Employee } from '../api/client';

const inputCls = "w-full rounded-btn border border-border bg-surface-1 px-3 py-2 text-[13px] text-txt-1 placeholder:text-txt-4 focus:border-accent/40 focus:outline-none transition-colors";

export default function KPI() {
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
