import { useEffect, useState, useCallback } from 'react';
import { ListTodo, Clock, AlertTriangle, CheckCircle, Plus } from 'lucide-react';
import StatCard from '../components/ui/StatCard';
import FilterChips from '../components/ui/FilterChips';
import StatusBadge from '../components/ui/StatusBadge';
import Modal from '../components/Modal';
import { getTasks, createTask, updateTask, deleteTask, dispatchTask, getEmployees, getGoals,
  type Task, type Employee, type Goal } from '../api/client';

const STATUS_FILTERS = [
  { label: '全部', value: '' }, { label: '待处理', value: 'pending' }, { label: '已派发', value: 'dispatched' },
  { label: '进行中', value: 'in_progress' }, { label: '已逾期', value: 'overdue' }, { label: '已完成', value: 'done' },
];
const EMPTY_FORM = { title: '', description: '', assignee_name: '', assignee_id: undefined as number | undefined, deadline: '', priority: 'normal' as 'normal' | 'high' | 'urgent', goal_id: undefined as number | undefined };
const inputCls = "w-full rounded-btn border border-border bg-surface-1 px-3 py-2 text-[13px] text-txt-1 placeholder:text-txt-4 focus:border-accent/40 focus:outline-none transition-colors";

export default function Tasks() {
  const [tasks, setTasks] = useState<Task[]>([]);
  const [employees, setEmployees] = useState<Employee[]>([]);
  const [goals, setGoals] = useState<Goal[]>([]);
  const [loading, setLoading] = useState(true);
  const [filterStatus, setFilterStatus] = useState('');
  const [modalOpen, setModalOpen] = useState(false);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [form, setForm] = useState(EMPTY_FORM);
  const [saving, setSaving] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const params: Record<string, string> = {}; if (filterStatus) params.status = filterStatus;
      const [t, e, g] = await Promise.all([getTasks(params), getEmployees().catch(() => []), getGoals().catch(() => [])]);
      setTasks(Array.isArray(t) ? t : []); setEmployees(Array.isArray(e) ? e : []); setGoals(Array.isArray(g) ? g : []);
    } catch { setTasks([]); }
    setLoading(false);
  }, [filterStatus]);
  useEffect(() => { load(); }, [load]);

  const stats = { pending: tasks.filter(t => t.status === 'pending').length, in_progress: tasks.filter(t => ['dispatched', 'in_progress'].includes(t.status || '')).length, overdue: tasks.filter(t => t.status === 'overdue').length, done: tasks.filter(t => t.status === 'done').length };
  const openCreate = () => { setEditingId(null); setForm(EMPTY_FORM); setModalOpen(true); };
  const openEdit = (t: Task) => { setEditingId(t.id); setForm({ title: t.title, description: t.description || '', assignee_name: t.assignee_name || '', assignee_id: t.assignee_id, deadline: t.deadline || '', priority: (t.priority || 'normal') as 'normal' | 'high' | 'urgent', goal_id: t.goal_id }); setModalOpen(true); };
  const save = async () => { setSaving(true); try { if (editingId) await updateTask(editingId, form); else await createTask(form); setModalOpen(false); load(); } catch (e) { alert(String(e)); } setSaving(false); };
  const handleDispatch = async (id: number) => { await dispatchTask(id); load(); };
  const handleDelete = async (id: number) => { if (confirm('确认删除？')) { await deleteTask(id); load(); } };

  return (
    <div className="space-y-5">
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <StatCard label="待处理" value={stats.pending} icon={<ListTodo className="w-4 h-4" />} />
        <StatCard label="进行中" value={stats.in_progress} accent="text-amber-600" icon={<Clock className="w-4 h-4" />} />
        <StatCard label="已逾期" value={stats.overdue} accent="text-red-600" icon={<AlertTriangle className="w-4 h-4" />} />
        <StatCard label="已完成" value={stats.done} accent="text-emerald-700" icon={<CheckCircle className="w-4 h-4" />} />
      </div>
      <div className="flex items-center justify-between">
        <FilterChips label="状态" options={STATUS_FILTERS} value={filterStatus} onChange={setFilterStatus} />
        <button onClick={openCreate} className="flex items-center gap-1.5 px-3 py-1.5 text-[13px] font-medium bg-accent text-white rounded-btn hover:bg-accent-hover transition-colors"><Plus className="w-3.5 h-3.5" /> 创建任务</button>
      </div>
      {loading ? <div className="text-center py-12 text-txt-4 text-[13px]">加载中...</div> : (
        <div className="rounded-card border border-border bg-surface-1 overflow-hidden">
          <table className="min-w-full text-[13px]">
            <thead><tr className="border-b border-border text-left text-[11px] font-medium text-txt-4 uppercase tracking-wider bg-surface-0/60">
              <th className="px-4 py-3">任务</th><th className="px-4 py-3">负责人</th><th className="px-4 py-3">状态</th><th className="px-4 py-3">优先级</th><th className="px-4 py-3">截止日期</th><th className="px-4 py-3 text-right">操作</th>
            </tr></thead>
            <tbody className="divide-y divide-border-subtle">
              {tasks.map(t => (
                <tr key={t.id} className="hover:bg-surface-3/40 transition-colors">
                  <td className="px-4 py-3"><div className="font-medium text-txt-1 truncate max-w-xs">{t.title}</div>{t.description && <div className="text-[11px] text-txt-4 truncate max-w-xs mt-0.5">{t.description}</div>}</td>
                  <td className="px-4 py-3 text-txt-3">{t.assignee_name || '未指派'}</td>
                  <td className="px-4 py-3"><StatusBadge status={t.status || 'pending'} /></td>
                  <td className="px-4 py-3"><StatusBadge status={t.priority || 'normal'} /></td>
                  <td className="px-4 py-3 text-txt-3">{t.deadline || '-'}</td>
                  <td className="px-4 py-3 text-right"><div className="flex items-center justify-end gap-3">
                    {t.status === 'pending' && <button onClick={() => handleDispatch(t.id)} className="text-[12px] text-accent hover:text-accent-hover transition-colors">派发</button>}
                    <button onClick={() => openEdit(t)} className="text-[12px] text-txt-4 hover:text-txt-2 transition-colors">编辑</button>
                    <button onClick={() => handleDelete(t.id)} className="text-[12px] text-red-400 hover:text-red-600 transition-colors">删除</button>
                  </div></td>
                </tr>
              ))}
              {tasks.length === 0 && <tr><td colSpan={6} className="px-4 py-12 text-center text-txt-4 text-[13px]">暂无任务数据</td></tr>}
            </tbody>
          </table>
        </div>
      )}
      <Modal open={modalOpen} onClose={() => setModalOpen(false)} title={editingId ? '编辑任务' : '创建任务'}
        footer={<><button onClick={() => setModalOpen(false)} className="px-3 py-1.5 text-[13px] border border-border rounded-btn text-txt-3 hover:bg-surface-3 transition-colors">取消</button>
          <button onClick={save} disabled={saving || !form.title} className="px-3 py-1.5 text-[13px] bg-accent text-white rounded-btn hover:bg-accent-hover disabled:opacity-40 transition-colors">{saving ? '保存中...' : '保存'}</button></>}>
        <div className="space-y-4">
          <div><label className="block text-[12px] font-medium text-txt-3 mb-1.5">任务标题 <span className="text-red-500">*</span></label><input value={form.title} onChange={e => setForm({...form, title: e.target.value})} className={inputCls} /></div>
          <div><label className="block text-[12px] font-medium text-txt-3 mb-1.5">描述</label><textarea value={form.description} onChange={e => setForm({...form, description: e.target.value})} rows={3} className={inputCls} /></div>
          <div className="grid grid-cols-2 gap-3">
            <div><label className="block text-[12px] font-medium text-txt-3 mb-1.5">负责人</label><select value={form.assignee_id || ''} onChange={e => { const emp = employees.find(emp => emp.id === Number(e.target.value)); setForm({...form, assignee_id: emp?.id, assignee_name: emp?.name || ''}); }} className={inputCls}><option value="">未指派</option>{employees.map(e => <option key={e.id} value={e.id}>{e.name}</option>)}</select></div>
            <div><label className="block text-[12px] font-medium text-txt-3 mb-1.5">优先级</label><select value={form.priority} onChange={e => setForm({...form, priority: e.target.value as 'normal' | 'high' | 'urgent'})} className={inputCls}><option value="normal">普通</option><option value="high">高</option><option value="urgent">紧急</option></select></div>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div><label className="block text-[12px] font-medium text-txt-3 mb-1.5">截止日期</label><input type="date" value={form.deadline} onChange={e => setForm({...form, deadline: e.target.value})} className={inputCls} /></div>
            <div><label className="block text-[12px] font-medium text-txt-3 mb-1.5">关联目标</label><select value={form.goal_id || ''} onChange={e => setForm({...form, goal_id: e.target.value ? Number(e.target.value) : undefined})} className={inputCls}><option value="">无</option>{goals.map(g => <option key={g.id} value={g.id}>{g.title}</option>)}</select></div>
          </div>
        </div>
      </Modal>
    </div>
  );
}
