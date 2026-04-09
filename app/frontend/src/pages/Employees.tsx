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
    try { const e = await getEmployees(); setEmployees(Array.isArray(e) ? e : []); }
    catch { setEmployees([]); }
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
    try { if (editingId) await updateEmployee(editingId, form); else await createEmployee(form); setModalOpen(false); load(); }
    catch (e) { alert(String(e)); }
    setSaving(false);
  };

  const handleDelete = async (id: number) => { if (confirm('确认删除？')) { await deleteEmployee(id); load(); } };

  const toggleExpand = async (id: number) => {
    if (expandedId === id) { setExpandedId(null); return; }
    setExpandedId(id);
    try { const records = await getCoachingRecords(id); setCoaching(Array.isArray(records) ? records : []); }
    catch { setCoaching([]); }
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

  const inputCls = "w-full rounded-btn border border-border bg-[rgba(255,255,255,0.02)] px-3 py-2 text-[13px] text-txt-2 placeholder:text-txt-4 focus:border-accent/40 focus:outline-none transition-colors";

  return (
    <div className="space-y-5">
      <div className="grid grid-cols-2 lg:grid-cols-3 gap-3">
        <StatCard label="员工总数" value={employees.length} icon={<Users className="w-4 h-4" />} />
        <StatCard label="部门数" value={departments.length} accent="text-accent-light" />
      </div>

      <div className="rounded-card border border-border overflow-hidden">
        <div className="border-b border-border px-4 py-3 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <label className="text-[12px] text-txt-4">部门</label>
            <select value={filterDept} onChange={e => setFilterDept(e.target.value)} className={`${inputCls} !w-auto`}>
              <option value="">全部</option>
              {departments.map(d => <option key={d} value={d}>{d}</option>)}
            </select>
            {filterDept && (
              <button onClick={() => setFilterDept('')} className="text-[12px] text-accent-light hover:text-accent-hover transition-colors">清除</button>
            )}
          </div>
          <button onClick={openCreate} className="flex items-center gap-1.5 px-3 py-1.5 text-[13px] font-medium bg-accent text-white rounded-btn hover:bg-accent-hover transition-colors">
            <Plus className="w-3.5 h-3.5" /> 添加员工
          </button>
        </div>

        {loading ? (
          <div className="text-center py-12 text-txt-4 text-[13px]">加载中...</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-full text-[13px]">
              <thead>
                <tr className="border-b border-border text-left text-[11px] font-medium text-txt-4 uppercase tracking-wider">
                  <th className="px-4 py-3 w-8"></th>
                  <th className="px-4 py-3">姓名</th>
                  <th className="px-4 py-3">部门</th>
                  <th className="px-4 py-3">职位</th>
                  <th className="px-4 py-3">飞书 ID</th>
                  <th className="px-4 py-3">入职时间</th>
                  <th className="px-4 py-3 text-right">操作</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {filtered.map((emp) => (
                  <> 
                    <tr key={emp.id} className="hover:bg-[rgba(255,255,255,0.02)] transition-colors">
                      <td className="px-4 py-3">
                        <button onClick={() => toggleExpand(emp.id)} className="text-txt-4 hover:text-txt-2 transition-colors">
                          {expandedId === emp.id ? <ChevronDown className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />}
                        </button>
                      </td>
                      <td className="px-4 py-3 font-medium text-txt-1">{emp.name}</td>
                      <td className="px-4 py-3 text-txt-3">{emp.department || '-'}</td>
                      <td className="px-4 py-3 text-txt-3">{emp.position || '-'}</td>
                      <td className="px-4 py-3 text-[12px] text-txt-4 font-mono">{emp.feishu_id || '-'}</td>
                      <td className="px-4 py-3 text-txt-4 text-[12px]">{emp.created_at?.slice(0, 10)}</td>
                      <td className="px-4 py-3 text-right">
                        <div className="flex items-center justify-end gap-3">
                          <button onClick={() => openEdit(emp)} className="text-[12px] text-txt-4 hover:text-txt-2 transition-colors">编辑</button>
                          <button onClick={() => handleDelete(emp.id)} className="text-[12px] text-red-400/70 hover:text-red-400 transition-colors">删除</button>
                        </div>
                      </td>
                    </tr>
                    {expandedId === emp.id && (
                      <tr key={`expand-${emp.id}`}>
                        <td colSpan={7} className="bg-[rgba(255,255,255,0.02)] px-8 py-4 border-t border-border">
                          <div className="space-y-3">
                            <h4 className="text-[13px] font-semibold text-txt-2">辅导记录</h4>
                            {coaching.length > 0 ? coaching.map((c) => (
                              <div key={c.id} className="rounded-card border border-border bg-surface-2 p-3">
                                <div className="flex items-center gap-2 mb-1">
                                  <span className="inline-flex px-1.5 py-0.5 rounded-micro text-[11px] bg-accent/10 text-accent-light">{c.type}</span>
                                  <span className="text-[11px] text-txt-4">{c.created_at?.slice(0, 16)}</span>
                                </div>
                                <p className="text-[13px] text-txt-2">{c.content}</p>
                                {c.ai_suggestion && (
                                  <div className="mt-2 text-[12px] text-txt-3 bg-accent/5 border border-accent/10 rounded-btn p-2">
                                    AI 建议: {c.ai_suggestion}
                                  </div>
                                )}
                              </div>
                            )) : (
                              <div className="text-[12px] text-txt-4">暂无辅导记录</div>
                            )}
                            <div className="flex gap-2 items-end">
                              <div className="flex-1">
                                <input value={coachingForm.content} onChange={e => setCoachingForm({...coachingForm, content: e.target.value})}
                                  placeholder="添加辅导记录..." className={inputCls} />
                              </div>
                              <button onClick={addCoaching} disabled={!coachingForm.content}
                                className="px-3 py-2 text-[13px] font-medium bg-accent text-white rounded-btn hover:bg-accent-hover disabled:opacity-40 transition-colors">
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
                  <tr><td colSpan={7} className="px-4 py-12 text-center text-txt-4 text-[13px]">暂无员工数据</td></tr>
                )}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <Modal open={modalOpen} onClose={() => setModalOpen(false)} title={editingId ? '编辑员工' : '添加员工'}
        footer={<>
          <button onClick={() => setModalOpen(false)} className="px-3 py-1.5 text-[13px] border border-border rounded-btn text-txt-3 hover:bg-[rgba(255,255,255,0.04)] transition-colors">取消</button>
          <button onClick={save} disabled={saving || !form.name} className="px-3 py-1.5 text-[13px] bg-accent text-white rounded-btn hover:bg-accent-hover disabled:opacity-40 transition-colors">{saving ? '保存中...' : '保存'}</button>
        </>}>
        <div className="space-y-4">
          <div>
            <label className="block text-[12px] font-medium text-txt-3 mb-1.5">姓名 <span className="text-red-400">*</span></label>
            <input value={form.name} onChange={e => setForm({...form, name: e.target.value})} className={inputCls} />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-[12px] font-medium text-txt-3 mb-1.5">部门</label>
              <input value={form.department} onChange={e => setForm({...form, department: e.target.value})} className={inputCls} />
            </div>
            <div>
              <label className="block text-[12px] font-medium text-txt-3 mb-1.5">职位</label>
              <input value={form.position} onChange={e => setForm({...form, position: e.target.value})} className={inputCls} />
            </div>
          </div>
          <div>
            <label className="block text-[12px] font-medium text-txt-3 mb-1.5">飞书 ID</label>
            <input value={form.feishu_id} onChange={e => setForm({...form, feishu_id: e.target.value})} placeholder="ou_xxx" className={inputCls} />
          </div>
        </div>
      </Modal>
    </div>
  );
}
