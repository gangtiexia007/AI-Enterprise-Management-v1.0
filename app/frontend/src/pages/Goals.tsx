import { useEffect, useState, useCallback } from 'react';
import { Target, Plus, ChevronDown, ChevronRight } from 'lucide-react';
import StatCard from '../components/ui/StatCard';
import StatusBadge from '../components/ui/StatusBadge';
import Modal from '../components/Modal';
import { getGoals, createGoal, updateGoal, deleteGoal, type Goal } from '../api/client';

const EMPTY_FORM = { title: '', level: 'company', owner: '', target_value: 0, current_value: 0, unit: '', deadline: '', parent_id: null as number | null };

function GoalCard({ goal, allGoals, onEdit, onDelete, depth = 0 }: {
  goal: Goal; allGoals: Goal[]; onEdit: (g: Goal) => void; onDelete: (id: number) => void; depth?: number;
}) {
  const [expanded, setExpanded] = useState(true);
  const children = goal.children || [];
  const progress = goal.target_value && goal.target_value > 0
    ? Math.round((goal.current_value || 0) / goal.target_value * 100) : 0;

  return (
    <div className={depth > 0 ? 'ml-6 mt-2' : ''}>
      <div className="rounded-lg border border-gray-200 bg-white shadow-sm p-4 hover:shadow-md transition-shadow">
        <div className="flex items-start justify-between gap-3">
          <div className="flex items-start gap-2 flex-1 min-w-0">
            {children.length > 0 && (
              <button onClick={() => setExpanded(!expanded)} className="mt-1 text-gray-400 hover:text-gray-600">
                {expanded ? <ChevronDown className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />}
              </button>
            )}
            <div className="min-w-0 flex-1">
              <div className="flex items-center gap-2 flex-wrap">
                <span className="font-medium text-gray-800">{goal.title}</span>
                <StatusBadge status={goal.level || 'company'} />
                <StatusBadge status={goal.status || 'active'} />
              </div>
              {goal.owner && <div className="text-xs text-gray-500 mt-1">负责人: {goal.owner}</div>}
              <div className="mt-2 flex items-center gap-2">
                <div className="flex-1 h-2 rounded-full bg-gray-100 overflow-hidden max-w-xs">
                  <div className={`h-full rounded-full transition-all ${
                    progress >= 80 ? 'bg-green-500' : progress >= 50 ? 'bg-brand-500' : 'bg-amber-400'
                  }`} style={{ width: `${Math.min(progress, 100)}%` }} />
                </div>
                <span className="text-xs text-gray-600 tabular-nums w-16 text-right">
                  {goal.current_value}/{goal.target_value}{goal.unit} ({progress}%)
                </span>
              </div>
              {goal.deadline && <div className="text-xs text-gray-400 mt-1">截止: {goal.deadline}</div>}
            </div>
          </div>
          <div className="flex items-center gap-2 flex-shrink-0">
            <button onClick={() => onEdit(goal)} className="text-xs text-gray-500 hover:text-gray-700">编辑</button>
            <button onClick={() => onDelete(goal.id)} className="text-xs text-red-500 hover:text-red-700">删除</button>
          </div>
        </div>
      </div>
      {expanded && children.map((child) => (
        <GoalCard key={child.id} goal={child} allGoals={allGoals} onEdit={onEdit} onDelete={onDelete} depth={depth + 1} />
      ))}
    </div>
  );
}

export default function Goals() {
  const [goals, setGoals] = useState<Goal[]>([]);
  const [loading, setLoading] = useState(true);
  const [modalOpen, setModalOpen] = useState(false);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [form, setForm] = useState(EMPTY_FORM);
  const [saving, setSaving] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const g = await getGoals();
      setGoals(Array.isArray(g) ? g : []);
    } catch { setGoals([]); }
    setLoading(false);
  }, []);

  useEffect(() => { load(); }, [load]);

  const flatGoals = (list: Goal[]): Goal[] => list.flatMap(g => [g, ...flatGoals(g.children || [])]);
  const allFlat = flatGoals(goals);
  const rootGoals = goals.filter(g => !g.parent_id);
  const avgProgress = allFlat.length > 0
    ? Math.round(allFlat.reduce((sum, g) => sum + (g.progress || 0), 0) / allFlat.length) : 0;

  const openCreate = () => { setEditingId(null); setForm(EMPTY_FORM); setModalOpen(true); };
  const openEdit = (g: Goal) => {
    setEditingId(g.id);
    setForm({ title: g.title, level: g.level || 'company', owner: g.owner || '', target_value: g.target_value || 0, current_value: g.current_value || 0, unit: g.unit || '', deadline: g.deadline || '', parent_id: g.parent_id || null });
    setModalOpen(true);
  };

  const save = async () => {
    setSaving(true);
    try {
      if (editingId) await updateGoal(editingId, form);
      else await createGoal(form);
      setModalOpen(false);
      load();
    } catch (e) { alert(String(e)); }
    setSaving(false);
  };

  const handleDelete = async (id: number) => { if (confirm('确认删除？')) { await deleteGoal(id); load(); } };

  return (
    <div className="space-y-5">
      <div className="grid grid-cols-2 lg:grid-cols-3 gap-3">
        <StatCard label="目标总数" value={allFlat.length} borderColor="border-l-brand-500"
          icon={<Target className="w-5 h-5" />} iconBg="bg-brand-50 text-brand-600" />
        <StatCard label="平均达成率" value={`${avgProgress}%`} borderColor="border-l-emerald-500"
          valueColor="text-emerald-700" progress={avgProgress} progressColor="bg-emerald-500" />
        <StatCard label="进行中" value={allFlat.filter(g => g.status === 'active').length}
          borderColor="border-l-amber-400" valueColor="text-amber-600" />
      </div>

      <div className="flex items-center justify-end">
        <button onClick={openCreate} className="flex items-center gap-1.5 px-3 py-1.5 text-sm bg-brand-600 text-white rounded-md hover:bg-brand-700">
          <Plus className="w-4 h-4" /> 创建目标
        </button>
      </div>

      {loading ? (
        <div className="text-center py-12 text-gray-400">加载中...</div>
      ) : rootGoals.length === 0 ? (
        <div className="text-center py-16 text-gray-400">
          <Target className="w-12 h-12 mx-auto mb-3 text-gray-300" />
          <div className="text-sm font-semibold text-gray-600">暂无目标</div>
          <div className="text-xs text-gray-400 mt-1">点击上方按钮创建第一个目标</div>
        </div>
      ) : (
        <div className="space-y-3">
          {rootGoals.map((goal) => (
            <GoalCard key={goal.id} goal={goal} allGoals={allFlat} onEdit={openEdit} onDelete={handleDelete} />
          ))}
        </div>
      )}

      <Modal open={modalOpen} onClose={() => setModalOpen(false)} title={editingId ? '编辑目标' : '创建目标'}
        footer={<>
          <button onClick={() => setModalOpen(false)} className="px-3 py-1.5 text-sm border border-gray-300 rounded-md text-gray-600 hover:bg-gray-50">取消</button>
          <button onClick={save} disabled={saving || !form.title} className="px-3 py-1.5 text-sm bg-brand-600 text-white rounded-md hover:bg-brand-700 disabled:opacity-50">{saving ? '保存中...' : '保存'}</button>
        </>}>
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-600 mb-1">目标标题 <span className="text-red-500">*</span></label>
            <input value={form.title} onChange={e => setForm({...form, title: e.target.value})}
              className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-brand-500 focus:ring-1 focus:ring-brand-500 outline-none" />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-sm font-medium text-gray-600 mb-1">层级</label>
              <select value={form.level} onChange={e => setForm({...form, level: e.target.value})}
                className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-brand-500 focus:ring-1 focus:ring-brand-500 outline-none">
                <option value="company">公司级</option>
                <option value="department">部门级</option>
                <option value="individual">个人级</option>
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-600 mb-1">负责人</label>
              <input value={form.owner} onChange={e => setForm({...form, owner: e.target.value})}
                className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-brand-500 focus:ring-1 focus:ring-brand-500 outline-none" />
            </div>
          </div>
          <div className="grid grid-cols-3 gap-3">
            <div>
              <label className="block text-sm font-medium text-gray-600 mb-1">目标值</label>
              <input type="number" value={form.target_value} onChange={e => setForm({...form, target_value: Number(e.target.value)})}
                className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-brand-500 focus:ring-1 focus:ring-brand-500 outline-none" />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-600 mb-1">当前值</label>
              <input type="number" value={form.current_value} onChange={e => setForm({...form, current_value: Number(e.target.value)})}
                className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-brand-500 focus:ring-1 focus:ring-brand-500 outline-none" />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-600 mb-1">单位</label>
              <input value={form.unit} onChange={e => setForm({...form, unit: e.target.value})} placeholder="万元"
                className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-brand-500 focus:ring-1 focus:ring-brand-500 outline-none" />
            </div>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-sm font-medium text-gray-600 mb-1">截止日期</label>
              <input type="date" value={form.deadline} onChange={e => setForm({...form, deadline: e.target.value})}
                className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-brand-500 focus:ring-1 focus:ring-brand-500 outline-none" />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-600 mb-1">上级目标</label>
              <select value={form.parent_id || ''} onChange={e => setForm({...form, parent_id: e.target.value ? Number(e.target.value) : null})}
                className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-brand-500 focus:ring-1 focus:ring-brand-500 outline-none">
                <option value="">无 (顶级目标)</option>
                {allFlat.filter(g => g.id !== editingId).map(g => <option key={g.id} value={g.id}>{g.title}</option>)}
              </select>
            </div>
          </div>
        </div>
      </Modal>
    </div>
  );
}
