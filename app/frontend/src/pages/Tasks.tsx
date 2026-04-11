import { useEffect, useState, useCallback } from 'react';
import { ListTodo, Clock, AlertTriangle, CheckCircle, Link2, ClipboardList, RefreshCw, ChevronRight, User, Calendar, FileCheck, Send } from 'lucide-react';
import StatCard from '../components/ui/StatCard';
import FilterChips from '../components/ui/FilterChips';
import StatusBadge from '../components/ui/StatusBadge';
import { getTasks, updateTask, deleteTask, dispatchTask, completeTask, chatWithAgent,
  type Task } from '../api/client';

type ViewMode = 'list' | 'dispatch';

const STATUS_FILTERS = [
  { label: '全部', value: '' }, { label: '待处理', value: 'pending' }, { label: '已派发', value: 'dispatched' },
  { label: '进行中', value: 'in_progress' }, { label: '已逾期', value: 'overdue' }, { label: '已完成', value: 'done' },
];
const DISPATCH_TABS = [
  { label: '待派发', value: 'pending' },
  { label: '已派发', value: 'dispatched' },
  { label: '待回收', value: 'in_progress' },
  { label: '已升级', value: 'overdue' },
];
const inputCls = "w-full rounded-btn border border-border bg-surface-1 px-3 py-2 text-[13px] text-txt-1 placeholder:text-txt-4 focus:border-accent/40 focus:outline-none transition-colors";

export default function Tasks() {
  const [viewMode, setViewMode] = useState<ViewMode>('list');
  const [tasks, setTasks] = useState<Task[]>([]);
  const [loading, setLoading] = useState(true);
  const [filterStatus, setFilterStatus] = useState('');

  const [nlInput, setNlInput] = useState('');
  const [nlCreating, setNlCreating] = useState(false);
  const [nlReply, setNlReply] = useState('');

  const [dispatchTab, setDispatchTab] = useState('pending');
  const [selectedTask, setSelectedTask] = useState<Task | null>(null);
  const [recovering, setRecovering] = useState(false);

  const activeStatus = viewMode === 'dispatch' ? dispatchTab : filterStatus;

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const params: Record<string, string> = {};
      if (activeStatus) params.status = activeStatus;
      const t = await getTasks(params);
      setTasks(Array.isArray(t) ? t : []);
    } catch { setTasks([]); }
    setLoading(false);
  }, [activeStatus]);
  useEffect(() => { load(); }, [load]);
  useEffect(() => { setSelectedTask(null); }, [dispatchTab]);

  const stats = {
    pending: tasks.filter(t => t.status === 'pending').length,
    in_progress: tasks.filter(t => ['dispatched', 'in_progress'].includes(t.status || '')).length,
    overdue: tasks.filter(t => t.status === 'overdue').length,
    done: tasks.filter(t => t.status === 'done').length,
  };

  const handleNlCreate = async () => {
    if (!nlInput.trim() || nlCreating) return;
    setNlCreating(true);
    setNlReply('');
    try {
      const prompt = `请帮我创建一个任务：${nlInput.trim()}。请调用 create_task 技能来创建，不要只回复文字。`;
      const res = await chatWithAgent(prompt);
      setNlReply(res.content || '任务已创建');
      setNlInput('');
      setTimeout(() => load(), 500);
    } catch (e) {
      setNlReply(`创建失败: ${e instanceof Error ? e.message : String(e)}`);
    }
    setNlCreating(false);
  };

  const handleDispatch = async (id: number) => { await dispatchTask(id); load(); };
  const handleComplete = async (id: number) => { await completeTask(id); load(); };
  const handleDelete = async (id: number) => { if (confirm('确认删除？')) { await deleteTask(id); load(); } };

  const handleRecoveryCheck = async () => {
    setRecovering(true);
    try { await new Promise(r => setTimeout(r, 1000)); load(); } catch { /* */ }
    setRecovering(false);
  };

  return (
    <div className="space-y-5">
      {/* View mode toggle */}
      <div className="flex gap-0 border-b border-border">
        <button onClick={() => { setViewMode('list'); setFilterStatus(''); }}
          className={`flex items-center gap-2 px-4 py-3 text-[13px] font-medium border-b-2 transition-colors ${viewMode === 'list' ? 'border-accent text-accent' : 'border-transparent text-txt-4 hover:text-txt-2'}`}>
          <ListTodo className="w-4 h-4" />任务列表
        </button>
        <button onClick={() => { setViewMode('dispatch'); setDispatchTab('pending'); }}
          className={`flex items-center gap-2 px-4 py-3 text-[13px] font-medium border-b-2 transition-colors ${viewMode === 'dispatch' ? 'border-accent text-accent' : 'border-transparent text-txt-4 hover:text-txt-2'}`}>
          <ClipboardList className="w-4 h-4" />调度视图
        </button>
      </div>

      {viewMode === 'list' && (
        <>
          <div className="rounded-card border border-border bg-surface-1 p-4">
            <div className="flex items-end gap-3">
              <div className="flex-1">
                <label className="block text-[12px] font-medium text-txt-3 mb-1.5">用自然语言创建任务</label>
                <input
                  value={nlInput}
                  onChange={e => setNlInput(e.target.value)}
                  onKeyDown={e => { if (e.key === 'Enter') handleNlCreate(); }}
                  placeholder="例如：给小王分配选品研究任务，下周三截止，优先级高"
                  className={inputCls}
                />
              </div>
              <button
                onClick={handleNlCreate}
                disabled={nlCreating || !nlInput.trim()}
                className="flex items-center gap-1.5 px-4 py-2 text-[13px] font-medium bg-accent text-white rounded-btn hover:bg-accent-hover disabled:opacity-40 transition-colors"
              >
                <Send className="w-3.5 h-3.5" />
                {nlCreating ? '创建中...' : 'AI 创建'}
              </button>
            </div>
            {nlReply && (
              <div className="mt-3 p-3 rounded-btn bg-surface-0 text-[12px] text-txt-2 whitespace-pre-wrap">{nlReply}</div>
            )}
          </div>
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
            <StatCard label="待处理" value={stats.pending} icon={<ListTodo className="w-4 h-4" />} />
            <StatCard label="进行中" value={stats.in_progress} accent="text-amber-600" icon={<Clock className="w-4 h-4" />} />
            <StatCard label="已逾期" value={stats.overdue} accent="text-red-600" icon={<AlertTriangle className="w-4 h-4" />} />
            <StatCard label="已完成" value={stats.done} accent="text-emerald-700" icon={<CheckCircle className="w-4 h-4" />} />
          </div>
          <FilterChips label="状态" options={STATUS_FILTERS} value={filterStatus} onChange={setFilterStatus} />

          {loading ? <div className="text-center py-12 text-txt-4 text-[13px]">加载中...</div> : (
            <div className="rounded-card border border-border bg-surface-1 overflow-hidden">
              <table className="min-w-full text-[13px]">
                <thead><tr className="border-b border-border text-left text-[11px] font-medium text-txt-4 uppercase tracking-wider bg-surface-0/60">
                  <th className="px-4 py-3">任务</th><th className="px-4 py-3">类型</th><th className="px-4 py-3">负责人</th><th className="px-4 py-3">状态</th><th className="px-4 py-3">优先级</th><th className="px-4 py-3">截止日期</th><th className="px-4 py-3 text-right">操作</th>
                </tr></thead>
                <tbody className="divide-y divide-border-subtle">
                  {tasks.map(t => (
                    <tr key={t.id} className="hover:bg-surface-3/40 transition-colors">
                      <td className="px-4 py-3">
                        <div className="font-medium text-txt-1 truncate max-w-xs">{t.title}</div>
                        {t.description && <div className="text-[11px] text-txt-4 truncate max-w-xs mt-0.5">{t.description}</div>}
                        {t.parent_task_id && <div className="flex items-center gap-1 text-[10px] text-accent mt-0.5"><Link2 className="w-3 h-3" /> 自动链任务</div>}
                      </td>
                      <td className="px-4 py-3 text-txt-3">{t.task_type ? <span className="inline-block px-2 py-0.5 text-[11px] rounded-full bg-indigo-50 text-indigo-700 dark:bg-indigo-900/30 dark:text-indigo-300">{t.task_type}</span> : '-'}</td>
                      <td className="px-4 py-3 text-txt-3">{t.assignee_name || '未指派'}</td>
                      <td className="px-4 py-3"><StatusBadge status={t.status || 'pending'} /></td>
                      <td className="px-4 py-3"><StatusBadge status={t.priority || 'normal'} /></td>
                      <td className="px-4 py-3 text-txt-3">{t.deadline || '-'}</td>
                      <td className="px-4 py-3 text-right"><div className="flex items-center justify-end gap-3">
                        {t.status === 'pending' && <button onClick={() => handleDispatch(t.id)} className="text-[12px] text-accent hover:text-accent-hover transition-colors">派发</button>}
                        {t.status && !['done', 'pending'].includes(t.status) && <button onClick={() => handleComplete(t.id)} className="text-[12px] text-emerald-600 hover:text-emerald-700 transition-colors">完成</button>}
                        <button onClick={() => handleDelete(t.id)} className="text-[12px] text-red-400 hover:text-red-600 transition-colors">删除</button>
                      </div></td>
                    </tr>
                  ))}
                  {tasks.length === 0 && <tr><td colSpan={7} className="px-4 py-12 text-center text-txt-4 text-[13px]">暂无任务数据</td></tr>}
                </tbody>
              </table>
            </div>
          )}
        </>
      )}

      {viewMode === 'dispatch' && (
        <>
          <div className="flex items-center justify-between">
            <FilterChips label="状态" options={DISPATCH_TABS} value={dispatchTab} onChange={setDispatchTab} />
            <button
              onClick={handleRecoveryCheck}
              disabled={recovering}
              className="flex items-center gap-1.5 px-3 py-1.5 text-[13px] font-medium border border-border text-txt-3 rounded-btn hover:bg-surface-3 disabled:opacity-40 transition-colors"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${recovering ? 'animate-spin' : ''}`} />
              回收检查
            </button>
          </div>

          {loading ? (
            <div className="text-center py-12 text-txt-4 text-[13px]">加载中...</div>
          ) : (
            <div className="grid grid-cols-1 lg:grid-cols-5 gap-4" style={{ minHeight: 480 }}>
              <div className="lg:col-span-2 rounded-card border border-border bg-surface-1 overflow-hidden flex flex-col">
                <div className="border-b border-border-subtle px-4 py-3">
                  <h3 className="text-[13px] font-semibold text-txt-1">
                    任务列表
                    <span className="text-txt-4 font-normal ml-2">{tasks.length} 项</span>
                  </h3>
                </div>
                <div className="flex-1 overflow-y-auto divide-y divide-border-subtle scrollbar-thin">
                  {tasks.length > 0 ? tasks.map(t => (
                    <div
                      key={t.id}
                      onClick={() => setSelectedTask(t)}
                      className={`px-4 py-3 cursor-pointer transition-colors ${
                        selectedTask?.id === t.id ? 'bg-accent-soft' : 'hover:bg-surface-3/50'
                      }`}
                    >
                      <div className="flex items-center justify-between gap-2">
                        <span className="text-[13px] font-medium text-txt-1 truncate">{t.title}</span>
                        <ChevronRight className="w-3 h-3 text-txt-4 flex-shrink-0" />
                      </div>
                      <div className="mt-1.5 flex items-center gap-2 flex-wrap">
                        <StatusBadge status={t.status || 'pending'} />
                        <StatusBadge status={t.priority || 'normal'} />
                        {t.assignee_name && (
                          <span className="text-[11px] text-txt-4 flex items-center gap-0.5">
                            <User className="w-3 h-3" />{t.assignee_name}
                          </span>
                        )}
                      </div>
                    </div>
                  )) : (
                    <div className="px-4 py-12 text-center text-[13px] text-txt-4">
                      {dispatchTab === 'pending' ? '暂无待派发任务' : '暂无任务'}
                    </div>
                  )}
                </div>
              </div>

              <div className="lg:col-span-3 rounded-card border border-border bg-surface-1 overflow-hidden flex flex-col">
                <div className="border-b border-border-subtle px-4 py-3">
                  <h3 className="text-[13px] font-semibold text-txt-1">任务详情</h3>
                </div>
                {selectedTask ? (
                  <div className="flex-1 overflow-y-auto p-4 space-y-4">
                    <div>
                      <h4 className="text-[15px] font-semibold text-txt-1">{selectedTask.title}</h4>
                      <div className="mt-2 flex items-center gap-2">
                        <StatusBadge status={selectedTask.status || 'pending'} />
                        <StatusBadge status={selectedTask.priority || 'normal'} />
                        {selectedTask.task_type && (
                          <span className="inline-block px-2 py-0.5 text-[11px] rounded-full bg-indigo-50 text-indigo-700 dark:bg-indigo-900/30 dark:text-indigo-300">
                            {selectedTask.task_type}
                          </span>
                        )}
                      </div>
                    </div>

                    <div className="grid grid-cols-2 gap-3">
                      <div className="rounded-btn bg-surface-0 p-3">
                        <div className="flex items-center gap-1.5 text-[11px] text-txt-4 mb-1">
                          <User className="w-3 h-3" />负责人
                        </div>
                        <div className="text-[13px] font-medium text-txt-1">{selectedTask.assignee_name || '未指派'}</div>
                      </div>
                      <div className="rounded-btn bg-surface-0 p-3">
                        <div className="flex items-center gap-1.5 text-[11px] text-txt-4 mb-1">
                          <Calendar className="w-3 h-3" />截止日期
                        </div>
                        <div className="text-[13px] font-medium text-txt-1">{selectedTask.deadline || '未设置'}</div>
                      </div>
                    </div>

                    {selectedTask.description && (
                      <div>
                        <div className="flex items-center gap-1.5 text-[12px] font-medium text-txt-3 mb-1.5">
                          <FileCheck className="w-3.5 h-3.5" />任务描述
                        </div>
                        <div className="rounded-btn bg-surface-0 p-3 text-[13px] text-txt-2 whitespace-pre-wrap">
                          {selectedTask.description}
                        </div>
                      </div>
                    )}

                    {selectedTask.auto_next_config && (
                      <div>
                        <div className="text-[12px] font-medium text-txt-3 mb-1.5">验收标准</div>
                        <div className="rounded-btn bg-surface-0 p-3 text-[12px] text-txt-3 font-mono whitespace-pre-wrap">
                          {selectedTask.auto_next_config}
                        </div>
                      </div>
                    )}

                    <div className="text-[11px] text-txt-4">
                      创建于 {selectedTask.created_at?.slice(0, 16)}
                      {selectedTask.updated_at && ` | 更新于 ${selectedTask.updated_at.slice(0, 16)}`}
                    </div>
                  </div>
                ) : (
                  <div className="flex-1 flex items-center justify-center text-[13px] text-txt-4">
                    <div className="text-center">
                      <ClipboardList className="w-8 h-8 text-txt-4/30 mx-auto mb-2" />
                      <span>选择左侧任务查看详情</span>
                    </div>
                  </div>
                )}
              </div>
            </div>
          )}
        </>
      )}

    </div>
  );
}
