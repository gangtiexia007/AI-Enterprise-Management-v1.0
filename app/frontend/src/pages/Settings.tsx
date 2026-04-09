import { useEffect, useState, useCallback } from 'react';
import { Check } from 'lucide-react';
import { getSettings, updateSetting, initSettings, type Setting } from '../api/client';

type TabId = 'general' | 'model' | 'feishu' | 'prompt';
const TABS: { id: TabId; label: string }[] = [{ id: 'general', label: '基础设置' }, { id: 'model', label: 'AI 模型' }, { id: 'feishu', label: '飞书集成' }, { id: 'prompt', label: '自定义 Prompt' }];
const FIELD_DEFS: Record<TabId, { key: string; label: string; type?: string; placeholder?: string }[]> = {
  general: [{ key: 'company_name', label: '公司名称', placeholder: '我的公司' }, { key: 'escalation_intervals', label: '催办间隔 (小时)', placeholder: '24,48' }, { key: 'report_time', label: '日报推送时间', placeholder: '09:00' }, { key: 'token_budget_daily', label: 'Token 日预算', placeholder: '100000' }],
  model: [{ key: 'ai_base_url', label: 'API Base URL', placeholder: 'https://api.openai.com/v1' }, { key: 'ai_api_key', label: 'API Key', type: 'password', placeholder: 'sk-...' }, { key: 'ai_model_primary', label: '主模型', placeholder: 'gpt-4o-mini' }, { key: 'ai_model_fallback', label: '回退模型', placeholder: 'gpt-3.5-turbo' }],
  feishu: [{ key: 'feishu_app_id', label: 'App ID', placeholder: 'cli_xxx' }, { key: 'feishu_app_secret', label: 'App Secret', type: 'password', placeholder: '...' }, { key: 'feishu_enabled', label: '启用飞书', placeholder: 'false' }, { key: 'feishu_boss_id', label: '老板飞书 ID', placeholder: 'ou_xxx' }],
  prompt: [{ key: 'custom_prompt', label: '自定义系统指令', type: 'textarea', placeholder: '添加自定义指令，AI 会在每次对话中遵守...' }],
};
const inputCls = "flex-1 rounded-btn border border-border bg-surface-1 px-3 py-2 text-[13px] text-txt-1 placeholder:text-txt-4 focus:border-accent/40 focus:outline-none transition-colors";

export default function Settings() {
  const [settings, setSettings] = useState<Record<string, string>>({}); const [activeTab, setActiveTab] = useState<TabId>('general');
  const [loading, setLoading] = useState(true); const [savedKey, setSavedKey] = useState<string | null>(null);
  const load = useCallback(async () => { setLoading(true); try { await initSettings().catch(()=>{}); const list = await getSettings(); const map: Record<string,string> = {}; if (Array.isArray(list)) list.forEach((s: Setting) => { map[s.key] = s.value; }); setSettings(map); } catch {} setLoading(false); }, []);
  useEffect(() => { load(); }, [load]);
  const saveSetting = async (key: string) => { try { await updateSetting({ key, value: settings[key] || '' }); setSavedKey(key); setTimeout(() => setSavedKey(null), 1500); } catch (e) { alert(String(e)); } };
  const saveAll = async () => { for (const f of FIELD_DEFS[activeTab]) await updateSetting({ key: f.key, value: settings[f.key] || '' }); setSavedKey('_all'); setTimeout(() => setSavedKey(null), 1500); };

  return (
    <div className="space-y-5">
      <div className="rounded-card border border-border bg-surface-1 overflow-hidden">
        <div className="border-b border-border-subtle px-4"><div className="flex gap-0">{TABS.map(tab => (
          <button key={tab.id} onClick={() => setActiveTab(tab.id)} className={`px-4 py-3 text-[13px] font-medium border-b-2 transition-colors ${activeTab === tab.id ? 'border-accent text-accent' : 'border-transparent text-txt-4 hover:text-txt-2'}`}>{tab.label}</button>
        ))}</div></div>
        <div className="p-5">{loading ? <div className="text-center py-8 text-txt-4 text-[13px]">加载中...</div> : (
          <div className="space-y-5 max-w-xl">{FIELD_DEFS[activeTab].map(field => (
            <div key={field.key}><label className="block text-[12px] font-medium text-txt-3 mb-1.5">{field.label}</label>
              <div className="flex gap-2">
                {field.type === 'textarea' ? <textarea value={settings[field.key] || ''} onChange={e => setSettings({...settings, [field.key]: e.target.value})} placeholder={field.placeholder} rows={6} className={inputCls} />
                  : <input type={field.type || 'text'} value={settings[field.key] || ''} onChange={e => setSettings({...settings, [field.key]: e.target.value})} placeholder={field.placeholder} className={inputCls} />}
                <button onClick={() => saveSetting(field.key)} className="px-3 py-1.5 text-[13px] border border-border rounded-btn text-txt-3 hover:bg-surface-3 flex-shrink-0 transition-colors">{savedKey === field.key ? <Check className="w-4 h-4 text-emerald-600" /> : '保存'}</button>
              </div></div>))}
            <div className="pt-3 border-t border-border-subtle"><button onClick={saveAll} className="px-4 py-2 text-[13px] font-medium bg-accent text-white rounded-btn hover:bg-accent-hover transition-colors">{savedKey === '_all' ? '已保存 ✓' : '保存全部'}</button></div>
          </div>)}</div>
      </div>
    </div>
  );
}
