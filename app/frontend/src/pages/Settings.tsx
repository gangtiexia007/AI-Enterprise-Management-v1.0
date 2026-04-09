import { useEffect, useState, useCallback } from 'react';
import { Check, Play, ToggleLeft, ToggleRight } from 'lucide-react';
import {
  getSettings, updateSetting, initSettings,
  getTokenBudget, updateTokenBudget,
  getScheduledTasks, toggleScheduledTask, runScheduledTask,
  type Setting, type TokenBudgetInfo, type ScheduledTask,
} from '../api/client';

type TabId = 'general' | 'model' | 'feishu' | 'prompt' | 'budget' | 'scheduler';
const TABS: { id: TabId; label: string }[] = [
  { id: 'general', label: '基础设置' },
  { id: 'model', label: 'AI 模型' },
  { id: 'feishu', label: '飞书集成' },
  { id: 'prompt', label: '自定义 Prompt' },
  { id: 'budget', label: 'Token 预算' },
  { id: 'scheduler', label: '定时任务' },
];

const FIELD_DEFS: Record<string, { key: string; label: string; type?: string; placeholder?: string }[]> = {
  general: [
    { key: 'company_name', label: '公司名称', placeholder: '我的公司' },
    { key: 'escalation_intervals', label: '催办间隔 (小时)', placeholder: '24,48,72' },
    { key: 'report_time', label: '日报推送时间', placeholder: '09:00' },
    { key: 'kpi_alert_threshold', label: 'KPI 预警阈值', placeholder: '60' },
    { key: 'industry_preset', label: '行业模板 (sales/operations/service/tech/manufacturing)', placeholder: '' },
  ],
  model: [
    { key: 'ai_base_url', label: 'API Base URL', placeholder: 'https://api.openai.com/v1' },
    { key: 'ai_api_key', label: 'API Key', type: 'password', placeholder: 'sk-...' },
    { key: 'ai_model_primary', label: '主模型', placeholder: 'gpt-4o-mini' },
    { key: 'ai_model_fallback', label: '回退模型', placeholder: 'gpt-3.5-turbo' },
  ],
  feishu: [
    { key: 'feishu_app_id', label: 'App ID', placeholder: 'cli_xxx' },
    { key: 'feishu_app_secret', label: 'App Secret', type: 'password', placeholder: '...' },
    { key: 'feishu_enabled', label: '启用飞书 (true/false)', placeholder: 'false' },
    { key: 'feishu_boss_id', label: '老板飞书 Open ID', placeholder: 'ou_xxx' },
  ],
  prompt: [
    { key: 'custom_prompt', label: '自定义系统指令', type: 'textarea', placeholder: '添加自定义指令，AI 会在每次对话中遵守...' },
  ],
};

const inputCls = "flex-1 rounded-btn border border-border bg-surface-1 px-3 py-2 text-[13px] text-txt-1 placeholder:text-txt-4 focus:border-accent/40 focus:outline-none transition-colors";

export default function Settings() {
  const [settings, setSettings] = useState<Record<string, string>>({});
  const [activeTab, setActiveTab] = useState<TabId>('general');
  const [loading, setLoading] = useState(true);
  const [savedKey, setSavedKey] = useState<string | null>(null);
  const [budget, setBudget] = useState<{ monthly: TokenBudgetInfo; daily: TokenBudgetInfo } | null>(null);
  const [scheduledTasks, setScheduledTasks] = useState<ScheduledTask[]>([]);
  const [budgetEdit, setBudgetEdit] = useState({ monthly: '', daily: '' });

  const load = useCallback(async () => {
    setLoading(true);
    try {
      await initSettings().catch(() => {});
      const list = await getSettings();
      const map: Record<string, string> = {};
      if (Array.isArray(list)) list.forEach((s: Setting) => { map[s.key] = s.value; });
      setSettings(map);
    } catch {}
    setLoading(false);
  }, []);

  useEffect(() => { load(); }, [load]);

  useEffect(() => {
    if (activeTab === 'budget') {
      getTokenBudget().then(b => {
        setBudget(b);
        setBudgetEdit({ monthly: String(b.monthly.budget_tokens), daily: String(b.daily.budget_tokens) });
      }).catch(() => {});
    }
    if (activeTab === 'scheduler') {
      getScheduledTasks().then(setScheduledTasks).catch(() => {});
    }
  }, [activeTab]);

  const saveSetting = async (key: string) => {
    try {
      await updateSetting({ key, value: settings[key] || '' });
      setSavedKey(key);
      setTimeout(() => setSavedKey(null), 1500);
    } catch (e) { alert(String(e)); }
  };

  const saveAll = async () => {
    const fields = FIELD_DEFS[activeTab];
    if (!fields) return;
    for (const f of fields) await updateSetting({ key: f.key, value: settings[f.key] || '' });
    setSavedKey('_all');
    setTimeout(() => setSavedKey(null), 1500);
  };

  const saveBudget = async () => {
    try {
      await updateTokenBudget({
        monthly: parseInt(budgetEdit.monthly) || 5000000,
        daily: parseInt(budgetEdit.daily) || 200000,
      });
      const b = await getTokenBudget();
      setBudget(b);
      setSavedKey('_budget');
      setTimeout(() => setSavedKey(null), 1500);
    } catch (e) { alert(String(e)); }
  };

  const handleToggleTask = async (id: number) => {
    try {
      await toggleScheduledTask(id);
      const tasks = await getScheduledTasks();
      setScheduledTasks(tasks);
    } catch {}
  };

  const handleRunTask = async (id: number) => {
    try {
      const result = await runScheduledTask(id);
      alert(result.message || '已执行');
      const tasks = await getScheduledTasks();
      setScheduledTasks(tasks);
    } catch (e) { alert(String(e)); }
  };

  const renderBudgetTab = () => {
    if (!budget) return <div className="text-center py-8 text-txt-4 text-[13px]">加载中...</div>;
    const { monthly, daily } = budget;
    return (
      <div className="space-y-6 max-w-xl">
        <div>
          <h3 className="text-[13px] font-semibold text-txt-2 mb-3">月度预算</h3>
          <div className="rounded-card border border-border p-4 space-y-3">
            <div className="flex justify-between text-[13px]">
              <span className="text-txt-3">已用 / 预算</span>
              <span className="text-txt-1 font-medium">{monthly.used_tokens.toLocaleString()} / {monthly.budget_tokens.toLocaleString()}</span>
            </div>
            <div className="w-full bg-surface-3 rounded-full h-2">
              <div className={`h-2 rounded-full transition-all ${monthly.usage_pct >= 80 ? 'bg-red-500' : monthly.usage_pct >= 50 ? 'bg-amber-500' : 'bg-emerald-500'}`} style={{ width: `${Math.min(monthly.usage_pct, 100)}%` }} />
            </div>
            <div className="text-[12px] text-txt-4">{monthly.usage_pct}% 已使用 · 剩余 {monthly.remaining.toLocaleString()} tokens</div>
            <div className="flex gap-2 pt-2">
              <input type="number" value={budgetEdit.monthly} onChange={e => setBudgetEdit(p => ({ ...p, monthly: e.target.value }))} className={inputCls} placeholder="月预算 tokens" />
            </div>
          </div>
        </div>
        <div>
          <h3 className="text-[13px] font-semibold text-txt-2 mb-3">日预算</h3>
          <div className="rounded-card border border-border p-4 space-y-3">
            <div className="flex justify-between text-[13px]">
              <span className="text-txt-3">已用 / 预算</span>
              <span className="text-txt-1 font-medium">{daily.used_tokens.toLocaleString()} / {daily.budget_tokens.toLocaleString()}</span>
            </div>
            <div className="w-full bg-surface-3 rounded-full h-2">
              <div className={`h-2 rounded-full transition-all ${daily.usage_pct >= 80 ? 'bg-red-500' : daily.usage_pct >= 50 ? 'bg-amber-500' : 'bg-emerald-500'}`} style={{ width: `${Math.min(daily.usage_pct, 100)}%` }} />
            </div>
            <div className="text-[12px] text-txt-4">{daily.usage_pct}% 已使用 · 剩余 {daily.remaining.toLocaleString()} tokens</div>
            <div className="flex gap-2 pt-2">
              <input type="number" value={budgetEdit.daily} onChange={e => setBudgetEdit(p => ({ ...p, daily: e.target.value }))} className={inputCls} placeholder="日预算 tokens" />
            </div>
          </div>
        </div>
        <button onClick={saveBudget} className="px-4 py-2 text-[13px] font-medium bg-accent text-white rounded-btn hover:bg-accent-hover transition-colors">
          {savedKey === '_budget' ? '已保存 ✓' : '保存预算设置'}
        </button>
      </div>
    );
  };

  const renderSchedulerTab = () => {
    if (!scheduledTasks.length) return <div className="text-center py-8 text-txt-4 text-[13px]">加载中...</div>;
    return (
      <div className="space-y-3">
        {scheduledTasks.map(t => (
          <div key={t.id} className="flex items-center justify-between rounded-card border border-border p-4">
            <div className="flex-1">
              <div className="flex items-center gap-2">
                <span className={`w-2 h-2 rounded-full ${t.enabled ? 'bg-emerald-500' : 'bg-zinc-300'}`} />
                <span className="text-[13px] font-medium text-txt-1">{t.name}</span>
                <span className="text-[11px] text-txt-4 bg-surface-3 px-1.5 py-0.5 rounded">{t.task_type}</span>
              </div>
              <div className="text-[12px] text-txt-4 mt-1">
                {t.cron_expression}{t.last_run ? ` · 上次运行: ${new Date(t.last_run).toLocaleString()}` : ''}
              </div>
            </div>
            <div className="flex items-center gap-2">
              <button onClick={() => handleRunTask(t.id)} title="立即执行" className="p-1.5 rounded hover:bg-surface-3 text-txt-3 transition-colors">
                <Play className="w-4 h-4" />
              </button>
              <button onClick={() => handleToggleTask(t.id)} className="p-1.5 rounded hover:bg-surface-3 transition-colors">
                {t.enabled ? <ToggleRight className="w-5 h-5 text-emerald-600" /> : <ToggleLeft className="w-5 h-5 text-txt-4" />}
              </button>
            </div>
          </div>
        ))}
      </div>
    );
  };

  return (
    <div className="space-y-5">
      <div className="rounded-card border border-border bg-surface-1 overflow-hidden">
        <div className="border-b border-border-subtle px-4">
          <div className="flex gap-0 overflow-x-auto">
            {TABS.map(tab => (
              <button key={tab.id} onClick={() => setActiveTab(tab.id)} className={`px-4 py-3 text-[13px] font-medium border-b-2 transition-colors whitespace-nowrap ${activeTab === tab.id ? 'border-accent text-accent' : 'border-transparent text-txt-4 hover:text-txt-2'}`}>
                {tab.label}
              </button>
            ))}
          </div>
        </div>
        <div className="p-5">
          {activeTab === 'budget' ? renderBudgetTab()
            : activeTab === 'scheduler' ? renderSchedulerTab()
            : loading ? <div className="text-center py-8 text-txt-4 text-[13px]">加载中...</div>
            : (
              <div className="space-y-5 max-w-xl">
                {(FIELD_DEFS[activeTab] || []).map(field => (
                  <div key={field.key}>
                    <label className="block text-[12px] font-medium text-txt-3 mb-1.5">{field.label}</label>
                    <div className="flex gap-2">
                      {field.type === 'textarea'
                        ? <textarea value={settings[field.key] || ''} onChange={e => setSettings({ ...settings, [field.key]: e.target.value })} placeholder={field.placeholder} rows={6} className={inputCls} />
                        : <input type={field.type || 'text'} value={settings[field.key] || ''} onChange={e => setSettings({ ...settings, [field.key]: e.target.value })} placeholder={field.placeholder} className={inputCls} />
                      }
                      <button onClick={() => saveSetting(field.key)} className="px-3 py-1.5 text-[13px] border border-border rounded-btn text-txt-3 hover:bg-surface-3 flex-shrink-0 transition-colors">
                        {savedKey === field.key ? <Check className="w-4 h-4 text-emerald-600" /> : '保存'}
                      </button>
                    </div>
                  </div>
                ))}
                {FIELD_DEFS[activeTab] && (
                  <div className="pt-3 border-t border-border-subtle">
                    <button onClick={saveAll} className="px-4 py-2 text-[13px] font-medium bg-accent text-white rounded-btn hover:bg-accent-hover transition-colors">
                      {savedKey === '_all' ? '已保存 ✓' : '保存全部'}
                    </button>
                  </div>
                )}
              </div>
            )}
        </div>
      </div>
    </div>
  );
}
