import { useEffect, useState, useCallback } from 'react';
import { BarChart3, Plus } from 'lucide-react';
import StatCard from '../components/ui/StatCard';
import StatusBadge from '../components/ui/StatusBadge';
import FilterChips from '../components/ui/FilterChips';
import Modal from '../components/Modal';
import { getKPIs, getKPISummary, createKPI, deleteKPI, getEmployees,
  type KPIRecord, type KPISummary, type Employee } from '../api/client';

export default function KPI() {
  const [records, setRecords] = useState<KPIRecord[]>([]);
  const [summary, setSummary] = useState<KPISummary[]>([]);
  const [employees, setEmployees] = useState<Employee[]>([]);
  const [loading, setLoading] = useState(true);
  const [filterEmployee, setFilterEmployee] = useState('');
  const [modalOpen, setModalOpen] = useState(false);
  const [form, setForm] = useState({ employee_id: 0, employee_name: '', metric_name: '', target_value: 0, actual_value: 0, weight: 1.0, period: '' });
  const [saving, setSaving] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const params: Record<string, string> = {};
      if (filterEmployee) params.employee_id = filterEmployee;
      const [r, s, e] = await Promise.all([getKPIs(params), getKPISummary().catch(() => []), getEmployees().catch(() => [])]);
      setRecords(Array.isArray(r) ? r : []);
      setSummary(Array.isArray(s) ? s : []);
      setEmployees(Array.isArray(e) ? e : []);
    } catch { setRecords([]); }
    setLoading(false);
  }, [filterEmployee]);

  useEffect(() => { load(); }, [load]);

  const empFilters = [{ label: '全部', value: '' }, ...employees.map(e => ({ label: e.name, value: String(e.id) }))];
  const avgScore = summary.length > 0 ? Math.round(summary.reduce((s, r) => s + r.avg_score, 0) / summary.length) : 0;

  const grouped = records.reduce<Record<string, KPIRecord[]>>((acc, r) => {
    const key = r.employee_name || '未知';
    if (!acc[key]) acc[key] = [];
    acc[key].push(r);
    return acc;
  }, {});

  const save = async () => {
    setSaving(true);
    try {
      await createKPI(form);
      setModalOpen(false);
      load();
    } catch (e) { alert(String(e)); }
    setSaving(false);
  };

  const handleDelete = async (id: number) => { if (confirm('确认删除？')) { await deleteKPI(id); load(); } };

  return (
    <div className="space-y-5">
      <div className="grid grid-cols-2 lg:grid-cols-3 gap-3">
        <StatCard label="KPI 记录" value={records.length} borderColor="border-l-brand-500"
          icon={<BarChart3 className="w-5 h-5" />} iconBg="bg-brand-50 text-brand-600" />
        <StatCard label="平均分" value={avgScore} borderColor="border-l-emerald-500"
          valueColor="text-emerald-700" subtitle="全员平均绩效分" />
        <StatCard label="考核员工" value={summary.length} borderColor="border-l-indigo-500"
          valueColor="text-indigo-700" />
      </div>

      <div className="flex items-center justify-between">
        <FilterChips label="员工" options={empFilters} value={filterEmployee} onChange={setFilterEmployee} />
        <button onClick={() => { setForm({ employee_id: 0, employee_name: '', metric_name: '', target_value: 0, actual_value: 0, weight: 1.0, period: '' }); setModalOpen(true); }}
          className="flex items-center gap-1.5 px-3 py-1.5 text-sm bg-brand-600 text-white rounded-md hover:bg-brand-700">
          <Plus className="w-4 h-4" /> 新增 KPI
        </button>
      </div>

      {loading ? (
        <div className="text-center py-12 text-gray-400">加载中...</div>
      ) : Object.keys(grouped).length === 0 ? (
        <div className="text-center py-16 text-gray-400">
          <BarChart3 className="w-12 h-12 mx-auto mb-3 text-gray-300" />
          <div className="text-sm font-semibold text-gray-600">暂无 KPI 数据</div>
        </div>
      ) : (
        <div className="space-y-4">
          {Object.entries(grouped).map(([name, items]) => (
            <div key={name} className="rounded-lg border border-gray-200 bg-white shadow-sm overflow-hidden">
              <div className="border-b border-gray-200 px-4 py-2.5 bg-gray-50/80 flex items-center justify-between">
                <h3 className="text-sm font-semibold text-gray-800">{name}</h3>
                <span className="text-xs text-gray-400">{items.length} 项指标</span>
              </div>
              <div className="overflow-x-auto">
                <table className="min-w-full text-sm">
                  <thead>
                    <tr className="text-left text-xs text-gray-500">
                      <th className="px-4 py-2 font-medium">指标名称</th>
                      <th className="px-4 py-2 font-medium">周期</th>
                      <th className="px-4 py-2 font-medium text-right">目标</th>
                      <th className="px-4 py-2 font-medium text-right">实际</th>
                      <th className="px-4 py-2 font-medium text-right">得分</th>
                      <th className="px-4 py-2 font-medium">等级</th>
                      <th className="px-4 py-2 font-medium text-right">操作</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-100">
                    {items.map((r) => (
                      <tr key={r.id} className="hover:bg-gray-50/80">
                        <td className="px-4 py-2.5 font-medium text-gray-800">{r.metric_name}</td>
                        <td className="px-4 py-2.5"><span className="inline-flex px-1.5 py-0.5 rounded text-xs bg-gray-100 text-gray-600">{r.period || '-'}</span></td>
                        <td className="px-4 py-2.5 text-right text-gray-600">{r.target_value}</td>
                        <td className="px-4 py-2.5 text-right text-gray-600">{r.actual_value}</td>
                        <td className="px-4 py-2.5 text-right font-medium text-gray-800">{r.score}</td>
                        <td className="px-4 py-2.5"><StatusBadge status={r.grade || '-'} /></td>
                        <td className="px-4 py-2.5 text-right">
                          <button onClick={() => handleDelete(r.id)} className="text-xs text-red-500 hover:text-red-700">删除</button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          ))}
        </div>
      )}

      <Modal open={modalOpen} onClose={() => setModalOpen(false)} title="新增 KPI"
        footer={<>
          <button onClick={() => setModalOpen(false)} className="px-3 py-1.5 text-sm border border-gray-300 rounded-md text-gray-600 hover:bg-gray-50">取消</button>
          <button onClick={save} disabled={saving || !form.metric_name || !form.employee_id} className="px-3 py-1.5 text-sm bg-brand-600 text-white rounded-md hover:bg-brand-700 disabled:opacity-50">{saving ? '保存中...' : '创建'}</button>
        </>}>
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-600 mb-1">员工 <span className="text-red-500">*</span></label>
            <select value={form.employee_id} onChange={e => {
              const emp = employees.find(emp => emp.id === Number(e.target.value));
              setForm({...form, employee_id: Number(e.target.value), employee_name: emp?.name || ''});
            }} className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-brand-500 focus:ring-1 focus:ring-brand-500 outline-none">
              <option value={0}>选择员工</option>
              {employees.map(e => <option key={e.id} value={e.id}>{e.name}</option>)}
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-600 mb-1">指标名称 <span className="text-red-500">*</span></label>
            <input value={form.metric_name} onChange={e => setForm({...form, metric_name: e.target.value})}
              className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-brand-500 focus:ring-1 focus:ring-brand-500 outline-none" />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-sm font-medium text-gray-600 mb-1">考核周期</label>
              <input value={form.period} onChange={e => setForm({...form, period: e.target.value})} placeholder="2024-Q1"
                className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-brand-500 focus:ring-1 focus:ring-brand-500 outline-none" />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-600 mb-1">权重</label>
              <input type="number" step="0.1" value={form.weight} onChange={e => setForm({...form, weight: Number(e.target.value)})}
                className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-brand-500 focus:ring-1 focus:ring-brand-500 outline-none" />
            </div>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-sm font-medium text-gray-600 mb-1">目标值</label>
              <input type="number" value={form.target_value} onChange={e => setForm({...form, target_value: Number(e.target.value)})}
                className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-brand-500 focus:ring-1 focus:ring-brand-500 outline-none" />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-600 mb-1">实际值</label>
              <input type="number" value={form.actual_value} onChange={e => setForm({...form, actual_value: Number(e.target.value)})}
                className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-brand-500 focus:ring-1 focus:ring-brand-500 outline-none" />
            </div>
          </div>
        </div>
      </Modal>
    </div>
  );
}
