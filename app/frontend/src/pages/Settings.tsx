import { useEffect, useState, useCallback } from 'react';
import { Check, Play, ToggleLeft, ToggleRight, Plus, Trash2, Copy, CheckCheck, ExternalLink } from 'lucide-react';
import {
  getSettings, updateSetting, initSettings,
  getTokenBudget, updateTokenBudget,
  getScheduledTasks, toggleScheduledTask, runScheduledTask,
  getBitableConfig, updateBitableConfig, testBitableConnection, getBitableTables,
  type Setting, type TokenBudgetInfo, type ScheduledTask,
} from '../api/client';

type TabId = 'general' | 'model' | 'feishu' | 'prompt' | 'budget' | 'scheduler' | 'bitable';
const TABS: { id: TabId; label: string }[] = [
  { id: 'general', label: '基础设置' },
  { id: 'model', label: 'AI 模型' },
  { id: 'feishu', label: '飞书集成' },
  { id: 'prompt', label: '自定义 Prompt' },
  { id: 'budget', label: 'Token 预算' },
  { id: 'scheduler', label: '定时任务' },
  { id: 'bitable', label: '多维表格' },
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
  const [bitableToken, setBitableToken] = useState('');
  const [bitableMap, setBitableMap] = useState<Record<string, string>>({});
  const [bitableCatMap, setBitableCatMap] = useState<Record<string, string>>({});
  const [bitableLoading, setBitableLoading] = useState(false);
  const [bitableMsg, setBitableMsg] = useState<string | null>(null);
  const [newAlias, setNewAlias] = useState('');
  const [newTableId, setNewTableId] = useState('');
  const [newCat, setNewCat] = useState('B');
  const [webhookCopied, setWebhookCopied] = useState(false);

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
    if (activeTab === 'bitable') {
      setBitableLoading(true);
      setBitableMsg(null);
      getBitableConfig()
        .then((c) => {
          setBitableToken(c.base_token || '');
          setBitableMap(c.table_map || {});
          setBitableCatMap(c.category_map || {});
        })
        .catch(() => setBitableMsg('加载多维表格配置失败'))
        .finally(() => setBitableLoading(false));
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

  const webhookUrl = `${window.location.protocol}//${window.location.host}/api/feishu/webhook`;

  const copyWebhookUrl = async () => {
    try {
      await navigator.clipboard.writeText(webhookUrl);
      setWebhookCopied(true);
      setTimeout(() => setWebhookCopied(false), 2000);
    } catch {
      prompt('复制 Webhook URL：', webhookUrl);
    }
  };

  const renderFeishuTab = () => {
    const fields = FIELD_DEFS['feishu'] || [];
    return (
      <div className="space-y-6 max-w-xl">
        {/* Standard Feishu fields */}
        <div className="space-y-5">
          {fields.map(field => (
            <div key={field.key}>
              <label className="block text-[12px] font-medium text-txt-3 mb-1.5">{field.label}</label>
              <div className="flex gap-2">
                <input
                  type={field.type || 'text'}
                  value={settings[field.key] || ''}
                  onChange={e => setSettings({ ...settings, [field.key]: e.target.value })}
                  placeholder={field.placeholder}
                  className={inputCls}
                />
                <button onClick={() => saveSetting(field.key)} className="px-3 py-1.5 text-[13px] border border-border rounded-btn text-txt-3 hover:bg-surface-3 flex-shrink-0 transition-colors">
                  {savedKey === field.key ? <Check className="w-4 h-4 text-emerald-600" /> : '保存'}
                </button>
              </div>
            </div>
          ))}
          <div className="pt-3 border-t border-border-subtle">
            <button onClick={saveAll} className="px-4 py-2 text-[13px] font-medium bg-accent text-white rounded-btn hover:bg-accent-hover transition-colors">
              {savedKey === '_all' ? '已保存 ✓' : '保存全部'}
            </button>
          </div>
        </div>

        {/* Webhook URL section */}
        <div className="rounded-card border border-border bg-surface-2 p-4 space-y-3">
          <div className="flex items-center gap-2">
            <span className="text-[13px] font-semibold text-txt-1">飞书消息接收 Webhook</span>
            <span className="text-[11px] bg-emerald-100 text-emerald-700 px-2 py-0.5 rounded-full font-medium">在线</span>
          </div>
          <p className="text-[12px] text-txt-3 leading-relaxed">
            在飞书开发者后台 → 事件与回调 → 事件订阅，填入此 URL，即可让 AI 助理在飞书中收发消息。
          </p>
          <div className="flex items-center gap-2">
            <code className="flex-1 rounded border border-border bg-surface-1 px-3 py-2 text-[12px] font-mono text-accent break-all select-all">
              {webhookUrl}
            </code>
            <button
              onClick={copyWebhookUrl}
              className="flex-shrink-0 flex items-center gap-1.5 px-3 py-2 text-[12px] font-medium border border-border rounded-btn hover:bg-surface-3 transition-colors"
              title="复制 URL"
            >
              {webhookCopied ? <CheckCheck className="w-4 h-4 text-emerald-600" /> : <Copy className="w-4 h-4 text-txt-3" />}
              {webhookCopied ? '已复制' : '复制'}
            </button>
          </div>
          <div className="border-t border-border-subtle pt-3 space-y-1.5">
            <p className="text-[12px] font-medium text-txt-2">配置步骤：</p>
            <ol className="text-[12px] text-txt-3 space-y-1 list-decimal list-inside">
              <li>飞书开发者后台 → 事件与回调 → 事件配置 → 填入上方 URL</li>
              <li>添加事件：<code className="bg-surface-3 px-1 rounded text-[11px]">im.message.receive_v1</code>（接收消息）</li>
              <li>权限管理 → 开通 <code className="bg-surface-3 px-1 rounded text-[11px]">im:message</code> 和 <code className="bg-surface-3 px-1 rounded text-[11px]">im:message:send_as_bot</code></li>
              <li>发布版本后，在飞书直接给机器人发消息即可</li>
            </ol>
          </div>
          <a
            href="https://open.feishu.cn/document/server-docs/im-v1/event-subscription-configure-/subscribe-to-events"
            target="_blank"
            rel="noreferrer"
            className="inline-flex items-center gap-1 text-[12px] text-accent hover:underline"
          >
            查看飞书文档 <ExternalLink className="w-3 h-3" />
          </a>
        </div>
      </div>
    );
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

  const saveBitableConfig = async (
    overrideMap?: Record<string, string>,
    overrideCatMap?: Record<string, string>,
  ) => {
    setBitableMsg(null);
    try {
      await updateBitableConfig({
        base_token: bitableToken,
        table_map: overrideMap ?? bitableMap,
        category_map: overrideCatMap ?? bitableCatMap,
      });
      setBitableMsg('已保存');
      setTimeout(() => setBitableMsg(null), 2000);
    } catch (e) {
      setBitableMsg(String(e));
    }
  };

  const addBitableRow = async () => {
    const alias = newAlias.trim();
    if (!alias) { setBitableMsg('请填写别名'); return; }
    if (bitableMap[alias] !== undefined) { setBitableMsg(`别名「${alias}」已存在`); return; }
    const nextMap = { ...bitableMap, [alias]: newTableId.trim() };
    const nextCat = { ...bitableCatMap, [alias]: newCat };
    setBitableMap(nextMap);
    setBitableCatMap(nextCat);
    setNewAlias('');
    setNewTableId('');
    setNewCat('B');
    await saveBitableConfig(nextMap, nextCat);
  };

  const deleteBitableRow = async (alias: string) => {
    const nextMap = { ...bitableMap };
    const nextCat = { ...bitableCatMap };
    delete nextMap[alias];
    delete nextCat[alias];
    setBitableMap(nextMap);
    setBitableCatMap(nextCat);
    await saveBitableConfig(nextMap, nextCat);
  };

  const handleBitableTest = async () => {
    setBitableMsg(null);
    try {
      await saveBitableConfig();
      const r = await testBitableConnection();
      setBitableMsg(`连接成功，共 ${r.table_count} 张表`);
    } catch (e) {
      setBitableMsg(`连接失败: ${String(e)}`);
    }
  };

  const CAT_LABELS: Record<string, string> = { A: 'A 参考', B: 'B 业务', C: 'C 管理' };

  const autoFillTableIds = async () => {
    setBitableMsg(null);
    try {
      const tables = await getBitableTables();
      const next = { ...bitableMap };
      const aliases = Object.keys(next).sort();
      const used = new Set<string>();
      for (const alias of aliases) {
        const core = alias.replace(/表$/, '').trim();
        const hit = tables.find((t) => {
          const id = t.table_id || '';
          const n = (t.name || '').trim();
          if (!id || used.has(id)) return false;
          if (n === alias) return true;
          if (core && n.includes(core)) return true;
          return false;
        });
        if (hit?.table_id) {
          next[alias] = hit.table_id;
          used.add(hit.table_id);
        }
      }
      setBitableMap(next);
      setBitableMsg('已根据表名尝试匹配 table_id，请核对后保存');
    } catch (e) {
      setBitableMsg(String(e));
    }
  };

  const renderBitableTab = () => {
    if (bitableLoading) return <div className="text-center py-8 text-txt-4 text-[13px]">加载中...</div>;
    const aliases = Object.keys(bitableMap);
    return (
      <div className="space-y-6 max-w-3xl">
        {/* base_token */}
        <div>
          <label className="block text-[12px] font-medium text-txt-3 mb-1.5">Base app_token（多维表格 URL 中的 token）</label>
          <input
            type="text"
            value={bitableToken}
            onChange={(e) => setBitableToken(e.target.value)}
            placeholder="bascnxxxxxxxx 或 XR0xbMcv3a..."
            className={inputCls + ' w-full max-w-xl'}
          />
          <p className="text-[11px] text-txt-4 mt-1">飞书多维表格 URL：/base/<strong>app_token</strong>?table=...</p>
        </div>
        {bitableMsg && (
          <div className="text-[12px] rounded-btn border border-border bg-surface-2 px-3 py-2 text-txt-2">{bitableMsg}</div>
        )}
        <div className="flex flex-wrap gap-2">
          <button type="button" onClick={() => saveBitableConfig()} className="px-4 py-2 text-[13px] font-medium bg-accent text-white rounded-btn hover:bg-accent-hover">
            保存配置
          </button>
          <button type="button" onClick={handleBitableTest} className="px-4 py-2 text-[13px] border border-border rounded-btn hover:bg-surface-3">
            测试连接
          </button>
          <button type="button" onClick={autoFillTableIds} className="px-4 py-2 text-[13px] border border-border rounded-btn hover:bg-surface-3">
            自动检测 table_id
          </button>
        </div>

        {/* Table mapping — dynamic rows */}
        <div>
          <h3 className="text-[13px] font-semibold text-txt-2 mb-2">表映射 <span className="text-txt-4 font-normal">（可自由增删，无需改代码）</span></h3>
          <div className="rounded-card border border-border overflow-hidden mb-3">
            <table className="w-full text-[12px]">
              <thead className="bg-surface-2 text-txt-3 text-left">
                <tr>
                  <th className="px-3 py-2 font-medium w-32">别名</th>
                  <th className="px-3 py-2 font-medium">table_id</th>
                  <th className="px-3 py-2 font-medium w-24">分类</th>
                  <th className="px-3 py-2 w-10" />
                </tr>
              </thead>
              <tbody>
                {aliases.length === 0 && (
                  <tr><td colSpan={4} className="px-3 py-4 text-center text-txt-4">暂无映射，点击下方"添加"</td></tr>
                )}
                {aliases.map((a) => (
                  <tr key={a} className="border-t border-border-subtle">
                    <td className="px-3 py-2 text-txt-2 font-medium whitespace-nowrap">{a}</td>
                    <td className="px-3 py-1.5">
                      <input
                        type="text"
                        value={bitableMap[a] || ''}
                        onChange={(e) => setBitableMap({ ...bitableMap, [a]: e.target.value })}
                        className="w-full rounded border border-border bg-surface-1 px-2 py-1 text-[12px] font-mono"
                        placeholder="tblxxxx"
                      />
                    </td>
                    <td className="px-3 py-1.5">
                      <select
                        value={bitableCatMap[a] || 'B'}
                        onChange={(e) => setBitableCatMap({ ...bitableCatMap, [a]: e.target.value })}
                        className="w-full rounded border border-border bg-surface-1 px-2 py-1 text-[12px]"
                      >
                        {Object.entries(CAT_LABELS).map(([v, l]) => <option key={v} value={v}>{l}</option>)}
                      </select>
                    </td>
                    <td className="px-2 py-1.5 text-center">
                      <button type="button" onClick={() => deleteBitableRow(a)} className="p-1 rounded hover:bg-red-50 text-txt-4 hover:text-red-500 transition-colors" title="删除此行">
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Add new row */}
          <div className="flex gap-2 items-center flex-wrap">
            <input
              type="text"
              value={newAlias}
              onChange={(e) => setNewAlias(e.target.value)}
              placeholder="别名，如 店铺表"
              className="rounded-btn border border-border bg-surface-1 px-3 py-1.5 text-[12px] w-32"
            />
            <input
              type="text"
              value={newTableId}
              onChange={(e) => setNewTableId(e.target.value)}
              placeholder="table_id（tblxxxx，可留空）"
              className="rounded-btn border border-border bg-surface-1 px-3 py-1.5 text-[12px] font-mono flex-1 min-w-40"
            />
            <select
              value={newCat}
              onChange={(e) => setNewCat(e.target.value)}
              className="rounded-btn border border-border bg-surface-1 px-2 py-1.5 text-[12px] w-24"
            >
              {Object.entries(CAT_LABELS).map(([v, l]) => <option key={v} value={v}>{l}</option>)}
            </select>
            <button type="button" onClick={addBitableRow} className="inline-flex items-center gap-1.5 px-3 py-1.5 text-[12px] font-medium bg-accent text-white rounded-btn hover:bg-accent-hover">
              <Plus className="w-3.5 h-3.5" />添加
            </button>
          </div>
          <p className="text-[11px] text-txt-4 mt-2">分类：A=参考数据（员工/店铺/产品）B=业务数据（销售/财务）C=管理数据（任务/目标/KPI）</p>
        </div>
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
            : activeTab === 'bitable' ? renderBitableTab()
            : activeTab === 'feishu' ? renderFeishuTab()
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
