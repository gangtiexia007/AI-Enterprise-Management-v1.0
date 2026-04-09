import { useEffect, useState, useCallback } from 'react';
import { ListTodo, Clock, AlertTriangle, CheckCircle, Plus } from 'lucide-react';
import StatCard from '../components/ui/StatCard';
import FilterChips from '../components/ui/FilterChips';
import StatusBadge from '../components/ui/StatusBadge';
import Modal from '../components/Modal';
import { getTasks, createTask, updateTask, deleteTask, dispatchTask, getEmployees, getGoals,
  type Task, type Employee, type Goal } from '../api/client';

const STATUS_FILTERS = [
  { label: '全部', value: '' },
  { label: '待处理', value: 'pending' },
  { label: '已派发', value: 'dispatched' },
  { label: '进行中', value: 'in_progress' },
  { label: '已逾期', value: 'overdue' },
  { label: '已完成', value: 'done' },
];

const EMPTY_FORM = { title: '', description: '', assignee_name: '', assignee_id: undefined as number | undefined, deadline: '', priority: 'normal', goal_id: undefined as number | undefined };

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
      const params: Record<string, string> = {};
      if (filterStatus) params.status = filterStatus;
      const [t, e, g] = await Promise.all([getTasks(params), getEmployees().catch(() => []), getGoals().catch(() => [])]);
      setTasks(Array.isArray(t) ? t : []);
      setEmployees(Array.isArray(e) ? e : []);
      setGoals(Array.isArray(g) ? g : []);
    } catch { setTasks([]); }
    setLoading(false);
  }, [filterStatus]);

  useEffect(() => { load(); }, [load]);

  const stats = {
    pending: tasks.filter(t => t.status === 'pending').length,
    in_progress: tasks.filter(t => ['dispatched', 'in_progress'].includes(t.status || '')).length,
    overdue: tasks.filter(t => t.status === 'overdue').length,
    done: tasks.filter(t => t.status === 'done').length,
  };

  const openCreate = () => { setEditingId(null); setForm(EMPTY_FORM); setModalOpen(true); };
  const openEdit = (t: Task) => {
    setEditingId(t.id);
    setForm({ title: t.title, description: t.description || '', assignee_name: t.assignee_name || '', assignee_id: t.assignee_id, deadline: t.deadline || '', priority: t.priority || 'normal', goal_id: t.goal_id });
    setModalOpen(true);
  };

  const save = async () => {
    setSaving(true);
    try {
      if (editingId) await updateTask(editingId, form);
      else await createTask(form);
      setModalOpen(false);
      load();
    } catch (e) { alert(String(e)); }
    setSaving(false);
  };

  const handleDispatch = async (id: number) => { await dispatchTask(id); load(); };
  const handleDelete = async (id: number) => { if (confirm('确认删除？')) { await deleteTask(id); load(); } };

  return (
    <div className="space-y-5">
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <StatCard label="待处理" value={stats.pending} borderColor="border-l-gray-400" icon={<ListTodo className="w-5 h-5" />} iconBg="bg-gray-100 text-gray-600" />
        <StatCard label="进行中" value={stats.in_progress} borderColor="border-l-amber-400" valueColor="text-amber-600" icon={<Clock className="w-5 h-5" />} iconBg="bg-amber-50 text-amber-600" />
        <StatCard label="已逾期" value={stats.overdue} borderColor="border-l-red-500" valueColor="text-red-600" icon={<AlertTriangle className="w-5 h-5" />} iconBg="bg-red-50 text-red-600" />
        <StatCard label="已完成" value={stats.done} borderColor="border-l-green-500" valueColor="text-green-600" icon={<CheckCircle className="w-5 h-5" />} iconBg="bg-green-50 text-green-600" />
      </div>

      <div className="flex items-center justify-between">
        <FilterChips label="状态" options={STATUS_FILTERS} value={filterStatus} onChange={setFilterStatus} />
        <button onClick={openCreate} className="flex items-center gap-1.5 px-3 py-1.5 text-sm bg-brand-600 text-white rounded-md hover:bg-brand-700">
          <Plus className="w-4 h-4" /> 创建任务
        </button>
      </div>

      {loading ? (
        <div className="text-center py-12 text-gray-400">加载中...</div>
      ) : (
        <div className="rounded-lg border border-gray-200 bg-white shadow-sm overflow-hidden">
          <div className="overflow-x-auto">
            <table className="min-w-full text-sm">
              <thead>
                <tr className="border-b border-gray-200 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider bg-gray-50">
                  <th className="px-4 py-3">任务</th>
                  <th className="px-4 py-3">负责人</th>
                  <th className="px-4 py-3">状态</th>
                  <th className="px-4 py-3">优先级</th>
                  <th className="px-4 py-3">截止日期</th>
                  <th className="px-4 py-3 text-right">操作</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {tasks.map((t) => (
                  <tr key={t.id} className="hover:bg-gray-50/80">
                    <td className="px-4 py-3">
                      <div className="font-medium text-gray-800 truncate max-w-xs">{t.title}</div>
                      {t.description && <div className="text-xs text-gray-400 truncate max-w-xs">{t.description}</div>}
                    </td>
                    <td className="px-4 py-3 text-gray-600">{t.assignee_name || '未指派'}</td>
                    <td className="px-4 py-3"><StatusBadge status={t.status || 'pending'} /></td>
                    <td className="px-4 py-3"><StatusBadge status={t.priority || 'normal'} /></td>
                    <td className="px-4 py-3 text-gray-600">{t.deadline || '-'}</td>
                    <td className="px-4 py-3 text-right">
                      <div className="flex items-center justify-end gap-2">
                        {t.status === 'pending' && (
                          <button onClick={() => handleDispatch(t.id)} className="text-xs text-brand-600 hover:text-brand-800 font-medium">派发</button>
                        )}
                        <button onClick={() => openEdit(t)} className="text-xs text-gray-500 hover:text-gray-700">编辑</button>
                        <button onClick={() => handleDelete(t.id)} className="text-xs text-red-500 hover:text-red-700">删除</button>
                      </div>
                    </td>
                  </tr>
                ))}
                {tasks.length === 0 && (
                  <tr><td colSpan={6} className="px-4 py-12 text-center text-gray-400">暂无任务数据</td></tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}

      <Modal open={modalOpen} onClose={() => setModalOpen(false)} title={editingId ? '编辑任务' : '创建任务'}
        footer={<>
          <button onClick={() => setModalOpen(false)} className="px-3 py-1.5 text-sm border border-gray-300 rounded-md text-gray-600 hover:bg-gray-50">取消</button>
          <button onClick={save} disabled={saving || !form.title} className="px-3 py-1.5 text-sm bg-brand-600 text-white rounded-md hover:bg-brand-700 disabled:opacity-50">{saving ? '保存中...' : '保存'}</button>
        </>}>
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-600 mb-1">任务标题 <span className="text-red-500">*</span></label>
            <input value={form.title} onChange={e => setForm({...form, title: e.target.value})}
              className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-brand-500 focus:ring-1 focus:ring-brand-500 outline-none" />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-600 mb-1">描述</label>
            <textarea value={form.description} onChange={e => setForm({...form, description: e.target.value})} rows={3}
              className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-brand-500 focus:ring-1 focus:ring-brand-500 outline-none" />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-sm font-medium text-gray-600 mb-1">负责人</label>
              <select value={form.assignee_id || ''} onChange={e => {
                const emp = employees.find(emp => emp.id === Number(e.target.value));
                setForm({...form, assignee_id: emp?.id, assignee_name: emp?.name || ''});
              }} className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-brand-500 focus:ring-1 focus:ring-brand-500 outline-none">
                <option value="">未指派</option>
                {employees.map(e => <option key={e.id} value={e.id}>{e.name}</option>)}
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-600 mb-1">优先级</label>
              <select value={form.priority} onChange={e => setForm({...form, priority: e.target.value})}
                className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-brand-500 focus:ring-1 focus:ring-brand-500 outline-none">
                <option value="normal">普通</option>
                <option value="high">高</option>
                <option value="urgent">紧急</option>
              </select>
            </div>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-sm font-medium text-gray-600 mb-1">截止日期</label>
              <input type="date" value={form.deadline} onChange={e => setForm({...form, deadline: e.target.value})}
                className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-brand-500 focus:ring-1 focus:ring-brand-500 outline-none" />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-600 mb-1">关联目标</label>
              <select value={form.goal_id || ''} onChange={e => setForm({...form, goal_id: e.target.value ? Number(e.target.value) : undefined})}
                className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-brand-500 focus:ring-1 focus:ring-brand-500 outline-none">
                <option value="">无</option>
                {goals.map(g => <option key={g.id} value={g.id}>{g.title}</option>)}
              </select>
            </div>
          </div>
        </div>
      </Modal>
    </div>
  );
}
