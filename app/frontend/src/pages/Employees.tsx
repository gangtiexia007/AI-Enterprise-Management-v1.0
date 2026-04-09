import { useEffect, useState, useCallback } from 'react';
import { Users, Plus, ChevronDown, ChevronRight } from 'lucide-react';
import StatCard from '../components/ui/StatCard';
import Modal from '../components/Modal';
import { getEmployees, createEmployee, updateEmployee, deleteEmployee, getCoachingRecords, createCoachingRecord,
  type Employee, type CoachingRecord } from '../api/client';

const EMPTY_FORM = { name: '', department: '', position: '', feishu_id: '' };

export default function Employees() {
  const [employees, setEmployees] = useState<Employee[]>([]);
  const [loading, setLoading] = useState(true);
  const [modalOpen, setModalOpen] = useState(false);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [form, setForm] = useState(EMPTY_FORM);
  const [saving, setSaving] = useState(false);
  const [expandedId, setExpandedId] = useState<number | null>(null);
  const [coaching, setCoaching] = useState<CoachingRecord[]>([]);
  const [coachingForm, setCoachingForm] = useState({ type: 'general', content: '' });
  const [filterDept, setFilterDept] = useState('');

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const e = await getEmployees();
      setEmployees(Array.isArray(e) ? e : []);
    } catch { setEmployees([]); }
    setLoading(false);
  }, []);

  useEffect(() => { load(); }, [load]);

  const departments = [...new Set(employees.map(e => e.department).filter(Boolean))];
  const filtered = filterDept ? employees.filter(e => e.department === filterDept) : employees;

  const openCreate = () => { setEditingId(null); setForm(EMPTY_FORM); setModalOpen(true); };
  const openEdit = (e: Employee) => {
    setEditingId(e.id);
    setForm({ name: e.name, department: e.department || '', position: e.position || '', feishu_id: e.feishu_id || '' });
    setModalOpen(true);
  };

  const save = async () => {
    setSaving(true);
    try {
      if (editingId) await updateEmployee(editingId, form);
      else await createEmployee(form);
      setModalOpen(false);
      load();
    } catch (e) { alert(String(e)); }
    setSaving(false);
  };

  const handleDelete = async (id: number) => { if (confirm('确认删除？')) { await deleteEmployee(id); load(); } };

  const toggleExpand = async (id: number) => {
    if (expandedId === id) { setExpandedId(null); return; }
    setExpandedId(id);
    try {
      const records = await getCoachingRecords(id);
      setCoaching(Array.isArray(records) ? records : []);
    } catch { setCoaching([]); }
  };

  const addCoaching = async () => {
    if (!expandedId || !coachingForm.content) return;
    try {
      await createCoachingRecord({ employee_id: expandedId, ...coachingForm });
      const records = await getCoachingRecords(expandedId);
      setCoaching(Array.isArray(records) ? records : []);
      setCoachingForm({ type: 'general', content: '' });
    } catch (e) { alert(String(e)); }
  };

  return (
    <div className="space-y-5">
      <div className="grid grid-cols-2 lg:grid-cols-3 gap-3">
        <StatCard label="员工总数" value={employees.length} borderColor="border-l-brand-500"
          icon={<Users className="w-5 h-5" />} iconBg="bg-brand-50 text-brand-600" />
        <StatCard label="部门数" value={departments.length} borderColor="border-l-indigo-500" valueColor="text-indigo-700" />
      </div>

      <div className="rounded-lg border border-gray-200 bg-white shadow-sm overflow-hidden">
        {/* Filter bar */}
        <div className="border-b border-gray-200 px-4 py-3 flex items-center justify-between bg-gray-50/50">
          <div className="flex items-center gap-3">
            <label className="text-sm text-gray-500">部门</label>
            <select value={filterDept} onChange={e => setFilterDept(e.target.value)}
              className="rounded-md border border-gray-300 px-2 py-1 text-sm focus:border-brand-500 outline-none">
              <option value="">全部</option>
              {departments.map(d => <option key={d} value={d}>{d}</option>)}
            </select>
            {filterDept && (
              <button onClick={() => setFilterDept('')} className="text-xs text-brand-600 hover:text-brand-800">清除</button>
            )}
          </div>
          <button onClick={openCreate} className="flex items-center gap-1.5 px-3 py-1.5 text-sm bg-brand-600 text-white rounded-md hover:bg-brand-700">
            <Plus className="w-4 h-4" /> 添加员工
          </button>
        </div>

        {loading ? (
          <div className="text-center py-12 text-gray-400">加载中...</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-full text-sm">
              <thead>
                <tr className="border-b border-gray-200 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider bg-white">
                  <th className="px-4 py-3 w-8"></th>
                  <th className="px-4 py-3">姓名</th>
                  <th className="px-4 py-3">部门</th>
                  <th className="px-4 py-3">职位</th>
                  <th className="px-4 py-3">飞书 ID</th>
                  <th className="px-4 py-3">入职时间</th>
                  <th className="px-4 py-3 text-right">操作</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {filtered.map((emp) => (
                  <>
                    <tr key={emp.id} className="hover:bg-gray-50/80">
                      <td className="px-4 py-3">
                        <button onClick={() => toggleExpand(emp.id)} className="text-gray-400 hover:text-gray-600">
                          {expandedId === emp.id ? <ChevronDown className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />}
                        </button>
                      </td>
                      <td className="px-4 py-3 font-medium text-gray-800">{emp.name}</td>
                      <td className="px-4 py-3 text-gray-600">{emp.department || '-'}</td>
                      <td className="px-4 py-3 text-gray-600">{emp.position || '-'}</td>
                      <td className="px-4 py-3 text-xs text-gray-400 font-mono">{emp.feishu_id || '-'}</td>
                      <td className="px-4 py-3 text-gray-500 text-xs">{emp.created_at?.slice(0, 10)}</td>
                      <td className="px-4 py-3 text-right">
                        <div className="flex items-center justify-end gap-2">
                          <button onClick={() => openEdit(emp)} className="text-xs text-gray-500 hover:text-gray-700">编辑</button>
                          <button onClick={() => handleDelete(emp.id)} className="text-xs text-red-500 hover:text-red-700">删除</button>
                        </div>
                      </td>
                    </tr>
                    {expandedId === emp.id && (
                      <tr key={`expand-${emp.id}`}>
                        <td colSpan={7} className="bg-gray-50/80 px-8 py-4">
                          <div className="space-y-3">
                            <h4 className="text-sm font-semibold text-gray-700">辅导记录</h4>
                            {coaching.length > 0 ? coaching.map((c) => (
                              <div key={c.id} className="rounded border border-gray-200 bg-white p-3">
                                <div className="flex items-center gap-2 mb-1">
                                  <span className="inline-flex px-1.5 py-0.5 rounded text-xs bg-brand-100 text-brand-700">{c.type}</span>
                                  <span className="text-xs text-gray-400">{c.created_at?.slice(0, 16)}</span>
                                </div>
                                <p className="text-sm text-gray-700">{c.content}</p>
                                {c.ai_suggestion && (
                                  <div className="mt-2 text-xs text-gray-500 bg-blue-50 rounded p-2">
                                    AI 建议: {c.ai_suggestion}
                                  </div>
                                )}
                              </div>
                            )) : (
                              <div className="text-xs text-gray-400">暂无辅导记录</div>
                            )}
                            <div className="flex gap-2 items-end">
                              <div className="flex-1">
                                <input value={coachingForm.content} onChange={e => setCoachingForm({...coachingForm, content: e.target.value})}
                                  placeholder="添加辅导记录..."
                                  className="w-full rounded-md border border-gray-300 px-3 py-1.5 text-sm focus:border-brand-500 focus:ring-1 focus:ring-brand-500 outline-none" />
                              </div>
                              <button onClick={addCoaching} disabled={!coachingForm.content}
                                className="px-3 py-1.5 text-sm bg-gray-800 text-white rounded-md hover:bg-gray-900 disabled:opacity-50">
                                添加
                              </button>
                            </div>
                          </div>
                        </td>
                      </tr>
                    )}
                  </>
                ))}
                {filtered.length === 0 && (
                  <tr><td colSpan={7} className="px-4 py-12 text-center text-gray-400">暂无员工数据</td></tr>
                )}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <Modal open={modalOpen} onClose={() => setModalOpen(false)} title={editingId ? '编辑员工' : '添加员工'}
        footer={<>
          <button onClick={() => setModalOpen(false)} className="px-3 py-1.5 text-sm border border-gray-300 rounded-md text-gray-600 hover:bg-gray-50">取消</button>
          <button onClick={save} disabled={saving || !form.name} className="px-3 py-1.5 text-sm bg-brand-600 text-white rounded-md hover:bg-brand-700 disabled:opacity-50">{saving ? '保存中...' : '保存'}</button>
        </>}>
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-600 mb-1">姓名 <span className="text-red-500">*</span></label>
            <input value={form.name} onChange={e => setForm({...form, name: e.target.value})}
              className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-brand-500 focus:ring-1 focus:ring-brand-500 outline-none" />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-sm font-medium text-gray-600 mb-1">部门</label>
              <input value={form.department} onChange={e => setForm({...form, department: e.target.value})}
                className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-brand-500 focus:ring-1 focus:ring-brand-500 outline-none" />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-600 mb-1">职位</label>
              <input value={form.position} onChange={e => setForm({...form, position: e.target.value})}
                className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-brand-500 focus:ring-1 focus:ring-brand-500 outline-none" />
            </div>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-600 mb-1">飞书 ID</label>
            <input value={form.feishu_id} onChange={e => setForm({...form, feishu_id: e.target.value})} placeholder="ou_xxx"
              className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-brand-500 focus:ring-1 focus:ring-brand-500 outline-none" />
          </div>
        </div>
      </Modal>
    </div>
  );
}
