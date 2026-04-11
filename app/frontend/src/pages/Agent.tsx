import { useEffect, useState, useCallback } from 'react';
import { Puzzle, Plus, Trash2, ToggleLeft, ToggleRight, FlaskConical, Settings2, ChevronDown, ChevronUp, Brain } from 'lucide-react';
import Modal from '../components/Modal';
import {
  getSkills, createSkill, deleteSkill, toggleSkill, testSkill,
  getMultiAgentConfig, toggleAgent as toggleAgentApi,
  type SkillItem,
} from '../api/client';

type TabId = 'skills' | 'pod-agents';
const TABS: { id: TabId; label: string; icon: typeof Puzzle }[] = [
  { id: 'skills', label: 'Skills 管理', icon: Puzzle },
  { id: 'pod-agents', label: 'POD Agents', icon: Brain },
];
const inputCls = "w-full rounded-btn border border-border bg-surface-1 px-3 py-2 text-[13px] text-txt-1 placeholder:text-txt-4 focus:border-accent/40 focus:outline-none transition-colors";
const SKILL_TYPE_LABELS: Record<string, string> = { builtin: '内置', custom: '自定义', mcp: 'MCP' };

export default function AgentPage() {
  const [tab, setTab] = useState<TabId>('skills');

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
      {tab === 'skills' && <SkillsTab />}
      {tab === 'pod-agents' && <PodAgentsTab />}
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

interface AgentInfo {
  id: string;
  name: string;
  description: string;
  enabled: boolean;
}

const AGENT_DEFS: AgentInfo[] = [
  { id: 'A1', name: '路由总控 Agent', description: '解析用户指令，分类任务类型，选择执行路线', enabled: true },
  { id: 'A2', name: '数据门控 Agent', description: '检查所需数据是否充分，不足时标记缺失项', enabled: true },
  { id: 'A3', name: '细分赛道研究 Agent', description: '分析 micro-niche 可行性，十维评估', enabled: true },
  { id: 'A4', name: '选品 Agent', description: '根据赛道选品方向给出 SPU 建议', enabled: true },
  { id: 'A5', name: '文案与 Listing Agent', description: '生成标题、描述、关键词等 Listing 要素', enabled: true },
  { id: 'A6', name: '定价利润 Agent', description: '计算定价、利润率、促销策略', enabled: true },
  { id: 'A7', name: '广告投放 Agent', description: '关键词广告策略、出价建议', enabled: true },
  { id: 'A8', name: '数据分析 Agent', description: '日报/周报/月报数据汇总与趋势分析', enabled: true },
  { id: 'A9', name: '店铺诊断 Agent', description: '店铺健康度评估与改进建议', enabled: true },
  { id: 'A10', name: '竞对分析 Agent', description: '竞品对标分析与策略建议', enabled: true },
  { id: 'A11', name: '归因分析 Agent', description: '漏斗五层归因：曝光/点击/转化/利润/履约', enabled: true },
  { id: 'A12', name: '任务派发 Agent', description: '将决策结果转化为可执行任务并分配', enabled: true },
  { id: 'A13', name: '回收验收 Agent', description: '验证任务输出质量，不合格则打回', enabled: true },
  { id: 'A14', name: '复盘沉淀 Agent', description: '提炼 SOP、案例、反面教材等经验', enabled: true },
  { id: 'A15', name: '合规风控 Agent', description: '检测高风险表达、平台禁区与侵权', enabled: true },
  { id: 'A16', name: '市场情报 Agent', description: '监控平台政策变化与市场趋势', enabled: true },
];

function PodAgentsTab() {
  const [agents, setAgents] = useState<AgentInfo[]>(AGENT_DEFS);
  const [loading, setLoading] = useState(true);
  const [expandedId, setExpandedId] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    getMultiAgentConfig()
      .then(res => {
        if (res?.agents && Array.isArray(res.agents)) {
          const merged = AGENT_DEFS.map(def => {
            const remote = res.agents.find((a: AgentInfo) => a.id === def.id);
            return remote ? { ...def, ...remote } : def;
          });
          setAgents(merged);
        }
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  const toggleAgent = async (id: string) => {
    const agent = agents.find(a => a.id === id);
    if (!agent) return;
    const newEnabled = !agent.enabled;
    setAgents(prev => prev.map(a => a.id === id ? { ...a, enabled: newEnabled } : a));
    try {
      await toggleAgentApi(id, newEnabled);
    } catch {
      setAgents(prev => prev.map(a => a.id === id ? { ...a, enabled: !newEnabled } : a));
    }
  };

  if (loading) return <div className="text-center py-12 text-txt-4 text-[13px]">加载中...</div>;

  return (
    <div className="space-y-5">
      <div className="rounded-card border border-border bg-surface-1 p-4">
        <div className="flex items-center gap-2 mb-3">
          <Settings2 className="w-4 h-4 text-txt-3" />
          <h3 className="text-[13px] font-semibold text-txt-1">全局设置</h3>
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          <div>
            <label className="block text-[12px] font-medium text-txt-3 mb-1.5">默认模型</label>
            <input readOnly value="gpt-4o-mini"
              className="w-full rounded-btn border border-border bg-surface-0 px-3 py-2 text-[13px] text-txt-3" />
          </div>
          <div>
            <label className="block text-[12px] font-medium text-txt-3 mb-1.5">单次 Token 预算</label>
            <input readOnly value="8000"
              className="w-full rounded-btn border border-border bg-surface-0 px-3 py-2 text-[13px] text-txt-3" />
          </div>
          <div>
            <label className="block text-[12px] font-medium text-txt-3 mb-1.5">已启用 Agent 数</label>
            <input readOnly value={`${agents.filter(a => a.enabled).length} / ${agents.length}`}
              className="w-full rounded-btn border border-border bg-surface-0 px-3 py-2 text-[13px] text-txt-3" />
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-3">
        {agents.map(agent => {
          const isExpanded = expandedId === agent.id;
          return (
            <div
              key={agent.id}
              className={`rounded-card border bg-surface-1 overflow-hidden transition-all ${agent.enabled ? 'border-border' : 'border-border opacity-60'}`}
            >
              <div className="p-4">
                <div className="flex items-start justify-between gap-2">
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2">
                      <span className="inline-flex items-center justify-center h-6 w-6 rounded-micro bg-accent-soft text-accent text-[11px] font-bold flex-shrink-0">
                        {agent.id}
                      </span>
                      <span className="text-[13px] font-medium text-txt-1 truncate">{agent.name}</span>
                    </div>
                    <p className="text-[12px] text-txt-4 mt-1.5 line-clamp-2">{agent.description}</p>
                  </div>
                  <button onClick={() => toggleAgent(agent.id)} className="flex-shrink-0 mt-0.5">
                    {agent.enabled
                      ? <ToggleRight className="w-6 h-6 text-accent" />
                      : <ToggleLeft className="w-6 h-6 text-txt-4" />
                    }
                  </button>
                </div>
                <button
                  onClick={() => setExpandedId(isExpanded ? null : agent.id)}
                  className="mt-3 flex items-center gap-1 text-[11px] text-accent hover:text-accent-hover transition-colors"
                >
                  {isExpanded ? '收起' : '详情'}
                  {isExpanded ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
                </button>
              </div>
              {isExpanded && (
                <div className="border-t border-border-subtle px-4 py-3 bg-surface-0/50">
                  <div className="text-[11px] font-medium text-txt-4 mb-1">系统提示词</div>
                  <div className="text-[12px] text-txt-3 bg-surface-0 rounded-btn p-2 max-h-32 overflow-y-auto font-mono whitespace-pre-wrap">
                    {`你是 ${agent.name}(${agent.id})。\n${agent.description}\n\n请根据输入数据执行分析并输出结构化结果。`}
                  </div>
                  <div className="text-[11px] font-medium text-txt-4 mt-3 mb-1">可用工具</div>
                  <div className="flex flex-wrap gap-1">
                    {['read_bitable', 'write_memory', 'send_task'].map(tool => (
                      <span key={tool} className="inline-block px-1.5 py-0.5 text-[10px] rounded-micro bg-surface-3 text-txt-3">{tool}</span>
                    ))}
                  </div>
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
