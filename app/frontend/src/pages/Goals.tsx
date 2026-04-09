import { useEffect, useState, useCallback } from 'react';
import { Target, Plus, ChevronDown, ChevronRight } from 'lucide-react';
import StatCard from '../components/ui/StatCard';
import StatusBadge from '../components/ui/StatusBadge';
import Modal from '../components/Modal';
import { getGoals, createGoal, updateGoal, deleteGoal, type Goal } from '../api/client';

const EMPTY_FORM = { title: '', level: 'company' as 'company' | 'department' | 'individual', owner: '', target_value: 0, current_value: 0, unit: '', deadline: '', parent_id: null as number | null };
const inputCls = "w-full rounded-btn border border-border bg-surface-1 px-3 py-2 text-[13px] text-txt-1 placeholder:text-txt-4 focus:border-accent/40 focus:outline-none transition-colors";

function GoalCard({ goal, allGoals, onEdit, onDelete, depth = 0 }: { goal: Goal; allGoals: Goal[]; onEdit: (g: Goal) => void; onDelete: (id: number) => void; depth?: number }) {
  const [expanded, setExpanded] = useState(true);
  const children = goal.children || [];
  const progress = goal.target_value && goal.target_value > 0 ? Math.round((goal.current_value || 0) / goal.target_value * 100) : 0;

  return (
    <div className={depth > 0 ? 'ml-6 mt-2' : ''}>
      <div className="rounded-card border border-border bg-surface-1 p-4 hover:shadow-sm transition-all">
        <div className="flex items-start justify-between gap-3">
          <div className="flex items-start gap-2 flex-1 min-w-0">
            {children.length > 0 && <button onClick={() => setExpanded(!expanded)} className="mt-0.5 text-txt-4 hover:text-txt-2 transition-colors">{expanded ? <ChevronDown className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />}</button>}
            <div className="min-w-0 flex-1">
              <div className="flex items-center gap-2 flex-wrap">
                <span className="font-medium text-[14px] text-txt-1">{goal.title}</span>
                <StatusBadge status={goal.level || 'company'} />
                <StatusBadge status={goal.status || 'active'} />
              </div>
              {goal.owner && <div className="text-[12px] text-txt-4 mt-1">负责人: {goal.owner}</div>}
              <div className="mt-2.5 flex items-center gap-2">
                <div className="flex-1 h-1.5 rounded-full bg-surface-3 overflow-hidden max-w-xs">
                  <div className={`h-full rounded-full transition-all duration-500 ${progress >= 80 ? 'bg-emerald-500' : progress >= 50 ? 'bg-accent' : 'bg-amber-400'}`} style={{ width: `${Math.min(progress, 100)}%` }} />
                </div>
                <span className="text-[12px] text-txt-3 tabular-nums w-20 text-right">{goal.current_value}/{goal.target_value}{goal.unit} ({progress}%)</span>
              </div>
              {goal.deadline && <div className="text-[11px] text-txt-4 mt-1.5">截止: {goal.deadline}</div>}
            </div>
          </div>
          <div className="flex items-center gap-3 flex-shrink-0">
            <button onClick={() => onEdit(goal)} className="text-[12px] text-txt-4 hover:text-txt-2 transition-colors">编辑</button>
            <button onClick={() => onDelete(goal.id)} className="text-[12px] text-red-400 hover:text-red-600 transition-colors">删除</button>
          </div>
        </div>
      </div>
      {expanded && children.map(child => <GoalCard key={child.id} goal={child} allGoals={allGoals} onEdit={onEdit} onDelete={onDelete} depth={depth + 1} />)}
    </div>
  );
}

export default function Goals() {
  const [goals, setGoals] = useState<Goal[]>([]); const [loading, setLoading] = useState(true);
  const [modalOpen, setModalOpen] = useState(false); const [editingId, setEditingId] = useState<number | null>(null);
  const [form, setForm] = useState(EMPTY_FORM); const [saving, setSaving] = useState(false);
  const load = useCallback(async () => { setLoading(true); try { const g = await getGoals(); setGoals(Array.isArray(g) ? g : []); } catch { setGoals([]); } setLoading(false); }, []);
  useEffect(() => { load(); }, [load]);
  const flatGoals = (list: Goal[]): Goal[] => list.flatMap(g => [g, ...flatGoals(g.children || [])]);
  const allFlat = flatGoals(goals); const rootGoals = goals.filter(g => !g.parent_id);
  const avgProgress = allFlat.length > 0 ? Math.round(allFlat.reduce((sum, g) => sum + (g.progress || 0), 0) / allFlat.length) : 0;
  const openCreate = () => { setEditingId(null); setForm(EMPTY_FORM); setModalOpen(true); };
  const openEdit = (g: Goal) => { setEditingId(g.id); setForm({ title: g.title, level: (g.level || 'company') as 'company' | 'department' | 'individual', owner: g.owner || '', target_value: g.target_value || 0, current_value: g.current_value || 0, unit: g.unit || '', deadline: g.deadline || '', parent_id: g.parent_id || null }); setModalOpen(true); };
  const save = async () => { setSaving(true); try { if (editingId) await updateGoal(editingId, form); else await createGoal(form); setModalOpen(false); load(); } catch (e) { alert(String(e)); } setSaving(false); };
  const handleDelete = async (id: number) => { if (confirm('确认删除？')) { await deleteGoal(id); load(); } };

  return (
    <div className="space-y-5">
      <div className="grid grid-cols-2 lg:grid-cols-3 gap-3">
        <StatCard label="目标总数" value={allFlat.length} icon={<Target className="w-4 h-4" />} />
        <StatCard label="平均达成率" value={`${avgProgress}%`} accent="text-emerald-700" progress={avgProgress} />
        <StatCard label="进行中" value={allFlat.filter(g => g.status === 'active').length} accent="text-amber-600" />
      </div>
      <div className="flex items-center justify-end">
        <button onClick={openCreate} className="flex items-center gap-1.5 px-3 py-1.5 text-[13px] font-medium bg-accent text-white rounded-btn hover:bg-accent-hover transition-colors"><Plus className="w-3.5 h-3.5" /> 创建目标</button>
      </div>
      {loading ? <div className="text-center py-12 text-txt-4 text-[13px]">加载中...</div>
        : rootGoals.length === 0 ? <div className="text-center py-16"><Target className="w-10 h-10 mx-auto mb-3 text-txt-4" /><div className="text-[14px] font-medium text-txt-3">暂无目标</div><div className="text-[12px] text-txt-4 mt-1">点击上方按钮创建第一个目标</div></div>
        : <div className="space-y-3">{rootGoals.map(goal => <GoalCard key={goal.id} goal={goal} allGoals={allFlat} onEdit={openEdit} onDelete={handleDelete} />)}</div>}
      <Modal open={modalOpen} onClose={() => setModalOpen(false)} title={editingId ? '编辑目标' : '创建目标'}
        footer={<><button onClick={() => setModalOpen(false)} className="px-3 py-1.5 text-[13px] border border-border rounded-btn text-txt-3 hover:bg-surface-3 transition-colors">取消</button>
          <button onClick={save} disabled={saving || !form.title} className="px-3 py-1.5 text-[13px] bg-accent text-white rounded-btn hover:bg-accent-hover disabled:opacity-40 transition-colors">{saving ? '保存中...' : '保存'}</button></>}>
        <div className="space-y-4">
          <div><label className="block text-[12px] font-medium text-txt-3 mb-1.5">目标标题 <span className="text-red-500">*</span></label><input value={form.title} onChange={e => setForm({...form, title: e.target.value})} className={inputCls} /></div>
          <div className="grid grid-cols-2 gap-3">
            <div><label className="block text-[12px] font-medium text-txt-3 mb-1.5">层级</label><select value={form.level} onChange={e => setForm({...form, level: e.target.value as 'company' | 'department' | 'individual'})} className={inputCls}><option value="company">公司级</option><option value="department">部门级</option><option value="individual">个人级</option></select></div>
            <div><label className="block text-[12px] font-medium text-txt-3 mb-1.5">负责人</label><input value={form.owner} onChange={e => setForm({...form, owner: e.target.value})} className={inputCls} /></div>
          </div>
          <div className="grid grid-cols-3 gap-3">
            <div><label className="block text-[12px] font-medium text-txt-3 mb-1.5">目标值</label><input type="number" value={form.target_value} onChange={e => setForm({...form, target_value: Number(e.target.value)})} className={inputCls} /></div>
            <div><label className="block text-[12px] font-medium text-txt-3 mb-1.5">当前值</label><input type="number" value={form.current_value} onChange={e => setForm({...form, current_value: Number(e.target.value)})} className={inputCls} /></div>
            <div><label className="block text-[12px] font-medium text-txt-3 mb-1.5">单位</label><input value={form.unit} onChange={e => setForm({...form, unit: e.target.value})} placeholder="万元" className={inputCls} /></div>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div><label className="block text-[12px] font-medium text-txt-3 mb-1.5">截止日期</label><input type="date" value={form.deadline} onChange={e => setForm({...form, deadline: e.target.value})} className={inputCls} /></div>
            <div><label className="block text-[12px] font-medium text-txt-3 mb-1.5">上级目标</label><select value={form.parent_id || ''} onChange={e => setForm({...form, parent_id: e.target.value ? Number(e.target.value) : null})} className={inputCls}><option value="">无 (顶级目标)</option>{allFlat.filter(g => g.id !== editingId).map(g => <option key={g.id} value={g.id}>{g.title}</option>)}</select></div>
          </div>
        </div>
      </Modal>
    </div>
  );
}
