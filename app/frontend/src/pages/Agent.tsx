import { useEffect, useState, useCallback } from 'react';
import { Bot, Users, Puzzle, Plus, Trash2, ToggleLeft, ToggleRight, FlaskConical, Save, Check } from 'lucide-react';
import Modal from '../components/Modal';
import {
  getAgentConfig, updateAgentConfig,
  getSubAgents, createSubAgent, updateSubAgent, deleteSubAgent,
  getSkills, createSkill, deleteSkill, toggleSkill, testSkill,
  type AgentConfig, type SubAgent, type SkillItem,
} from '../api/client';

type TabId = 'overview' | 'sub-agents' | 'skills';
const TABS: { id: TabId; label: string; icon: typeof Bot }[] = [
  { id: 'overview', label: 'Agent 概览', icon: Bot },
  { id: 'sub-agents', label: '子 Agent', icon: Users },
  { id: 'skills', label: 'Skills 管理', icon: Puzzle },
];
const inputCls = "w-full rounded-btn border border-border bg-surface-1 px-3 py-2 text-[13px] text-txt-1 placeholder:text-txt-4 focus:border-accent/40 focus:outline-none transition-colors";
const SKILL_TYPE_LABELS: Record<string, string> = { builtin: '内置', custom: '自定义', mcp: 'MCP' };

export default function AgentPage() {
  const [tab, setTab] = useState<TabId>('overview');

  return (
    <div className="space-y-5">
      <div className="flex gap-0 border-b border-border">
        {TABS.map(t => (
          <button key={t.id} onClick={() => setTab(t.id)}
            className={`flex items-center gap-2 px-4 py-3 text-[13px] font-medium border-b-2 transition-colors ${tab === t.id ? 'border-accent text-accent' : 'border-transparent text-txt-4 hover:text-txt-2'}`}>
            <t.icon className="w-4 h-4" />{t.label}
          </button>
        ))}
      </div>
      {tab === 'overview' && <AgentOverview />}
      {tab === 'sub-agents' && <SubAgentsTab />}
      {tab === 'skills' && <SkillsTab />}
    </div>
  );
}

function AgentOverview() {
  const [config, setConfig] = useState<AgentConfig | null>(null);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  useEffect(() => { getAgentConfig().then(setConfig).catch(() => {}); }, []);

  const save = async () => {
    if (!config) return;
    setSaving(true);
    try {
      const updated = await updateAgentConfig({
        name: config.name,
        mode: config.mode,
        model_primary: config.model_primary,
        model_fallback: config.model_fallback,
        system_prompt: config.system_prompt,
        max_tokens: config.max_tokens,
      });
      setConfig(updated);
      setSaved(true);
      setTimeout(() => setSaved(false), 1500);
    } catch (e) { alert(String(e)); }
    setSaving(false);
  };

  if (!config) return <div className="text-center py-12 text-txt-4 text-[13px]">加载中...</div>;

  return (
    <div className="max-w-2xl space-y-5">
      <div className="rounded-card border border-border bg-surface-1 p-5 space-y-4">
        <div className="flex items-center gap-3 mb-2">
          <Bot className="w-5 h-5 text-accent" />
          <h3 className="text-[15px] font-semibold text-txt-1">Agent 配置</h3>
          <span className={`ml-auto inline-flex px-2 py-0.5 rounded-micro text-[11px] font-medium ${config.mode === 'full' ? 'bg-emerald-50 text-emerald-700' : config.mode === 'light' ? 'bg-amber-50 text-amber-700' : 'bg-gray-100 text-gray-600'}`}>
            {config.mode === 'full' ? '完整模式' : config.mode === 'light' ? '轻量模式' : '命令模式'}
          </span>
        </div>

        <div><label className="block text-[12px] font-medium text-txt-3 mb-1.5">Agent 名称</label>
          <input value={config.name} onChange={e => setConfig({...config, name: e.target.value})} className={inputCls} /></div>

        <div><label className="block text-[12px] font-medium text-txt-3 mb-1.5">运行模式</label>
          <div className="flex gap-2">
            {(['command', 'light', 'full'] as const).map(m => (
              <button key={m} onClick={() => setConfig({...config, mode: m})}
                className={`flex-1 px-3 py-2 text-[13px] font-medium rounded-btn border transition-colors ${config.mode === m ? 'border-accent bg-accent-soft text-accent' : 'border-border text-txt-3 hover:border-border-solid'}`}>
                {m === 'full' ? '完整模式' : m === 'light' ? '轻量模式' : '命令模式'}
                <div className="text-[10px] mt-0.5 font-normal text-txt-4">
                  {m === 'command' ? '零 Token' : m === 'light' ? '小模型+只读' : '全功能+工具'}
                </div>
              </button>
            ))}
          </div></div>

        <div className="grid grid-cols-2 gap-3">
          <div><label className="block text-[12px] font-medium text-txt-3 mb-1.5">主模型</label>
            <input value={config.model_primary} onChange={e => setConfig({...config, model_primary: e.target.value})} className={inputCls} /></div>
          <div><label className="block text-[12px] font-medium text-txt-3 mb-1.5">回退模型</label>
            <input value={config.model_fallback} onChange={e => setConfig({...config, model_fallback: e.target.value})} className={inputCls} /></div>
        </div>

        <div><label className="block text-[12px] font-medium text-txt-3 mb-1.5">Max Tokens</label>
          <input type="number" value={config.max_tokens} onChange={e => setConfig({...config, max_tokens: Number(e.target.value)})} className={inputCls} /></div>

        <div><label className="block text-[12px] font-medium text-txt-3 mb-1.5">系统 Prompt</label>
          <textarea value={config.system_prompt} onChange={e => setConfig({...config, system_prompt: e.target.value})} rows={5} placeholder="自定义系统指令..." className={inputCls} /></div>

        <button onClick={save} disabled={saving} className="flex items-center gap-1.5 px-4 py-2 text-[13px] font-medium bg-accent text-white rounded-btn hover:bg-accent-hover disabled:opacity-40 transition-colors">
          {saved ? <><Check className="w-3.5 h-3.5" /> 已保存</> : <><Save className="w-3.5 h-3.5" /> {saving ? '保存中...' : '保存配置'}</>}
        </button>
      </div>
    </div>
  );
}

function SubAgentsTab() {
  const [agents, setAgents] = useState<SubAgent[]>([]);
  const [loading, setLoading] = useState(true);
  const [modalOpen, setModalOpen] = useState(false);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [form, setForm] = useState({ role: 'director', name: '', description: '', model: '', allowed_tools: '[]', read_only: 1, can_spawn_children: 0, system_prompt: '' });
  const [saving, setSaving] = useState(false);

  const load = useCallback(async () => { setLoading(true); try { setAgents(await getSubAgents()); } catch { setAgents([]); } setLoading(false); }, []);
  useEffect(() => { load(); }, [load]);

  const openCreate = () => { setEditingId(null); setForm({ role: 'director', name: '', description: '', model: '', allowed_tools: '[]', read_only: 1, can_spawn_children: 0, system_prompt: '' }); setModalOpen(true); };
  const openEdit = (sa: SubAgent) => { setEditingId(sa.id); setForm({ role: sa.role, name: sa.name, description: sa.description, model: sa.model, allowed_tools: sa.allowed_tools, read_only: sa.read_only, can_spawn_children: sa.can_spawn_children, system_prompt: sa.system_prompt }); setModalOpen(true); };
  const save = async () => { setSaving(true); try { if (editingId) await updateSubAgent(editingId, form); else await createSubAgent(form); setModalOpen(false); load(); } catch (e) { alert(String(e)); } setSaving(false); };
  const handleDelete = async (id: number) => { if (confirm('确认删除？')) { await deleteSubAgent(id); load(); } };

  const roleColor: Record<string, string> = { director: 'bg-purple-50 text-purple-600', analyst: 'bg-blue-50 text-blue-600', coach: 'bg-emerald-50 text-emerald-700', executor: 'bg-amber-50 text-amber-700' };

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <p className="text-[13px] text-txt-3">管理子 Agent 角色，每个子 Agent 有独立的模型和权限配置。</p>
        <button onClick={openCreate} className="flex items-center gap-1.5 px-3 py-1.5 text-[13px] font-medium bg-accent text-white rounded-btn hover:bg-accent-hover transition-colors"><Plus className="w-3.5 h-3.5" /> 新建</button>
      </div>
      {loading ? <div className="text-center py-12 text-txt-4 text-[13px]">加载中...</div> : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          {agents.map(sa => (
            <div key={sa.id} className="rounded-card border border-border bg-surface-1 p-4 hover:shadow-sm transition-all">
              <div className="flex items-start justify-between gap-2">
                <div>
                  <div className="flex items-center gap-2">
                    <span className="text-[14px] font-semibold text-txt-1">{sa.name}</span>
                    <span className={`inline-flex px-1.5 py-0.5 rounded-micro text-[10px] font-medium ${roleColor[sa.role] || 'bg-gray-100 text-gray-600'}`}>{sa.role}</span>
                    {sa.read_only ? <span className="text-[10px] text-txt-4 border border-border-subtle rounded-micro px-1">只读</span> : null}
                  </div>
                  <p className="text-[12px] text-txt-3 mt-1">{sa.description || '暂无描述'}</p>
                  {sa.model && <p className="text-[11px] text-txt-4 mt-1">模型: {sa.model}</p>}
                </div>
                <div className="flex gap-2 flex-shrink-0">
                  <button onClick={() => openEdit(sa)} className="text-[12px] text-txt-4 hover:text-txt-2 transition-colors">编辑</button>
                  <button onClick={() => handleDelete(sa.id)} className="text-[12px] text-red-400 hover:text-red-600 transition-colors">删除</button>
                </div>
              </div>
              <div className="mt-2 text-[11px] text-txt-4">
                允许工具: {(() => { try { const t = JSON.parse(sa.allowed_tools); return t.length > 0 ? t.join(', ') : '全部'; } catch { return '全部'; } })()}
              </div>
            </div>
          ))}
          {agents.length === 0 && <div className="col-span-2 text-center py-12 text-txt-4 text-[13px]">暂无子 Agent</div>}
        </div>
      )}
      <Modal open={modalOpen} onClose={() => setModalOpen(false)} title={editingId ? '编辑子 Agent' : '新建子 Agent'} width="max-w-lg"
        footer={<><button onClick={() => setModalOpen(false)} className="px-3 py-1.5 text-[13px] border border-border rounded-btn text-txt-3 hover:bg-surface-3 transition-colors">取消</button>
          <button onClick={save} disabled={saving || !form.name} className="px-3 py-1.5 text-[13px] bg-accent text-white rounded-btn hover:bg-accent-hover disabled:opacity-40 transition-colors">{saving ? '保存中...' : '保存'}</button></>}>
        <div className="space-y-4">
          <div className="grid grid-cols-2 gap-3">
            <div><label className="block text-[12px] font-medium text-txt-3 mb-1.5">名称 <span className="text-red-500">*</span></label><input value={form.name} onChange={e => setForm({...form, name: e.target.value})} className={inputCls} /></div>
            <div><label className="block text-[12px] font-medium text-txt-3 mb-1.5">角色</label>
              <select value={form.role} onChange={e => setForm({...form, role: e.target.value})} className={inputCls}><option value="director">Director (总监)</option><option value="analyst">Analyst (分析师)</option><option value="coach">Coach (教练)</option><option value="executor">Executor (执行者)</option></select></div>
          </div>
          <div><label className="block text-[12px] font-medium text-txt-3 mb-1.5">描述</label><textarea value={form.description} onChange={e => setForm({...form, description: e.target.value})} rows={2} className={inputCls} /></div>
          <div><label className="block text-[12px] font-medium text-txt-3 mb-1.5">模型 (留空使用主 Agent 模型)</label><input value={form.model} onChange={e => setForm({...form, model: e.target.value})} placeholder="gpt-4o-mini" className={inputCls} /></div>
          <div><label className="block text-[12px] font-medium text-txt-3 mb-1.5">允许工具 (JSON 数组)</label><input value={form.allowed_tools} onChange={e => setForm({...form, allowed_tools: e.target.value})} placeholder='["today_tasks", "overdue_tasks"]' className={inputCls} /></div>
          <div className="flex gap-4">
            <label className="flex items-center gap-2 text-[13px] text-txt-2 cursor-pointer"><input type="checkbox" checked={!!form.read_only} onChange={e => setForm({...form, read_only: e.target.checked ? 1 : 0})} className="rounded" /> 只读模式</label>
            <label className="flex items-center gap-2 text-[13px] text-txt-2 cursor-pointer"><input type="checkbox" checked={!!form.can_spawn_children} onChange={e => setForm({...form, can_spawn_children: e.target.checked ? 1 : 0})} className="rounded" /> 可创建子Agent</label>
          </div>
          <div><label className="block text-[12px] font-medium text-txt-3 mb-1.5">自定义 Prompt</label><textarea value={form.system_prompt} onChange={e => setForm({...form, system_prompt: e.target.value})} rows={3} className={inputCls} /></div>
        </div>
      </Modal>
    </div>
  );
}

function SkillsTab() {
  const [skills, setSkills] = useState<SkillItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [filterType, setFilterType] = useState('');
  const [modalOpen, setModalOpen] = useState(false);
  const [testResult, setTestResult] = useState<{ skill: string; data: unknown } | null>(null);
  const [form, setForm] = useState({ name: '', type: 'custom' as 'custom' | 'mcp', description: '', config: '{}', permission_level: 0 });
  const [saving, setSaving] = useState(false);

  const load = useCallback(async () => { setLoading(true); try { setSkills(await getSkills(filterType || undefined)); } catch { setSkills([]); } setLoading(false); }, [filterType]);
  useEffect(() => { load(); }, [load]);

  const handleToggle = async (id: number) => { await toggleSkill(id); load(); };
  const handleDelete = async (id: number) => { if (confirm('确认删除？')) { try { await deleteSkill(id); load(); } catch (e) { alert(String(e)); } } };
  const handleTest = async (id: number) => { try { const r = await testSkill(id); setTestResult(r); } catch (e) { alert(String(e)); } };
  const save = async () => { setSaving(true); try { await createSkill(form); setModalOpen(false); load(); } catch (e) { alert(String(e)); } setSaving(false); };

  const typeFilters = [{ label: '全部', value: '' }, { label: '内置', value: 'builtin' }, { label: '自定义', value: 'custom' }, { label: 'MCP', value: 'mcp' }];
  const permLabels = ['P0 自动', 'P1 规则', 'P2 审批', 'P3 强审批', 'P4 禁止'];
  const typeBg: Record<string, string> = { builtin: 'bg-indigo-50 text-indigo-600', custom: 'bg-emerald-50 text-emerald-700', mcp: 'bg-purple-50 text-purple-600' };

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between flex-wrap gap-2">
        <div className="flex gap-1.5">
          {typeFilters.map(f => (
            <button key={f.value} onClick={() => setFilterType(f.value)}
              className={`px-2.5 py-1 text-[12px] font-medium rounded-pill border transition-colors ${filterType === f.value ? 'border-accent/40 bg-accent-soft text-accent' : 'border-border text-txt-3 hover:text-txt-2'}`}>{f.label}</button>
          ))}
        </div>
        <button onClick={() => { setForm({ name: '', type: 'custom', description: '', config: '{}', permission_level: 0 }); setModalOpen(true); }}
          className="flex items-center gap-1.5 px-3 py-1.5 text-[13px] font-medium bg-accent text-white rounded-btn hover:bg-accent-hover transition-colors"><Plus className="w-3.5 h-3.5" /> 添加 Skill</button>
      </div>
      {loading ? <div className="text-center py-12 text-txt-4 text-[13px]">加载中...</div> : (
        <div className="rounded-card border border-border bg-surface-1 overflow-hidden">
          <table className="min-w-full text-[13px]">
            <thead><tr className="border-b border-border text-left text-[11px] font-medium text-txt-4 uppercase tracking-wider bg-surface-0/60">
              <th className="px-4 py-3">Skill</th><th className="px-4 py-3 w-20">类型</th><th className="px-4 py-3 w-20">权限</th><th className="px-4 py-3 w-16">状态</th><th className="px-4 py-3 w-32 text-right">操作</th>
            </tr></thead>
            <tbody className="divide-y divide-border-subtle">
              {skills.map(s => (
                <tr key={s.id} className="hover:bg-surface-3/40 transition-colors">
                  <td className="px-4 py-3"><div className="font-medium text-txt-1">{s.name}</div><div className="text-[11px] text-txt-4 mt-0.5">{s.description || '-'}</div></td>
                  <td className="px-4 py-3"><span className={`inline-flex px-1.5 py-0.5 rounded-micro text-[10px] font-medium ${typeBg[s.type] || 'bg-gray-100 text-gray-600'}`}>{SKILL_TYPE_LABELS[s.type] || s.type}</span></td>
                  <td className="px-4 py-3"><span className="text-[11px] text-txt-3">{permLabels[s.permission_level] || `P${s.permission_level}`}</span></td>
                  <td className="px-4 py-3">
                    <button onClick={() => handleToggle(s.id)} className="text-txt-3 hover:text-accent transition-colors">
                      {s.enabled ? <ToggleRight className="w-5 h-5 text-emerald-600" /> : <ToggleLeft className="w-5 h-5 text-txt-4" />}
                    </button>
                  </td>
                  <td className="px-4 py-3 text-right">
                    <div className="flex items-center justify-end gap-3">
                      <button onClick={() => handleTest(s.id)} className="text-accent hover:text-accent-hover transition-colors" title="测试"><FlaskConical className="w-3.5 h-3.5" /></button>
                      {s.type !== 'builtin' && <button onClick={() => handleDelete(s.id)} className="text-red-400 hover:text-red-600 transition-colors"><Trash2 className="w-3.5 h-3.5" /></button>}
                    </div>
                  </td>
                </tr>
              ))}
              {skills.length === 0 && <tr><td colSpan={5} className="px-4 py-12 text-center text-txt-4 text-[13px]">暂无 Skills</td></tr>}
            </tbody>
          </table>
        </div>
      )}
      <Modal open={!!testResult} onClose={() => setTestResult(null)} title={`测试结果: ${testResult?.skill || ''}`}>
        <pre className="text-[12px] text-txt-2 bg-surface-3/50 rounded-btn p-3 overflow-auto max-h-60 whitespace-pre-wrap">
          {JSON.stringify(testResult?.data, null, 2)}
        </pre>
      </Modal>
      <Modal open={modalOpen} onClose={() => setModalOpen(false)} title="添加 Skill"
        footer={<><button onClick={() => setModalOpen(false)} className="px-3 py-1.5 text-[13px] border border-border rounded-btn text-txt-3 hover:bg-surface-3 transition-colors">取消</button>
          <button onClick={save} disabled={saving || !form.name} className="px-3 py-1.5 text-[13px] bg-accent text-white rounded-btn hover:bg-accent-hover disabled:opacity-40 transition-colors">{saving ? '保存中...' : '创建'}</button></>}>
        <div className="space-y-4">
          <div className="grid grid-cols-2 gap-3">
            <div><label className="block text-[12px] font-medium text-txt-3 mb-1.5">名称 <span className="text-red-500">*</span></label><input value={form.name} onChange={e => setForm({...form, name: e.target.value})} className={inputCls} /></div>
            <div><label className="block text-[12px] font-medium text-txt-3 mb-1.5">类型</label>
              <select value={form.type} onChange={e => setForm({...form, type: e.target.value as 'custom' | 'mcp'})} className={inputCls}><option value="custom">自定义 (SKILL.md)</option><option value="mcp">MCP 外部工具</option></select></div>
          </div>
          <div><label className="block text-[12px] font-medium text-txt-3 mb-1.5">描述</label><input value={form.description} onChange={e => setForm({...form, description: e.target.value})} className={inputCls} /></div>
          <div><label className="block text-[12px] font-medium text-txt-3 mb-1.5">权限级别</label>
            <select value={form.permission_level} onChange={e => setForm({...form, permission_level: Number(e.target.value)})} className={inputCls}>
              {permLabels.map((l, i) => <option key={i} value={i}>{l}</option>)}
            </select></div>
          <div><label className="block text-[12px] font-medium text-txt-3 mb-1.5">{form.type === 'custom' ? 'SKILL.md 内容 (JSON: {"content": "..."})' : 'MCP 配置 (JSON: {"endpoint": "...", "auth": {...}})'}</label>
            <textarea value={form.config} onChange={e => setForm({...form, config: e.target.value})} rows={6} placeholder={form.type === 'custom' ? '{"content": "# My Skill\\n\\n步骤1..."}' : '{"endpoint": "http://localhost:8080/mcp", "auth": {"type": "bearer", "token": "..."}}'} className={inputCls + " font-mono text-[12px]"} /></div>
        </div>
      </Modal>
    </div>
  );
}
