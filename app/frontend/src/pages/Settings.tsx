import { useEffect, useState, useCallback } from 'react';
import { Settings as SettingsIcon, Check } from 'lucide-react';
import { getSettings, updateSetting, initSettings, type Setting } from '../api/client';

type TabId = 'general' | 'model' | 'feishu' | 'prompt';

const TABS: { id: TabId; label: string }[] = [
  { id: 'general', label: '基础设置' },
  { id: 'model', label: 'AI 模型' },
  { id: 'feishu', label: '飞书集成' },
  { id: 'prompt', label: '自定义 Prompt' },
];

const FIELD_DEFS: Record<TabId, { key: string; label: string; type?: string; placeholder?: string }[]> = {
  general: [
    { key: 'company_name', label: '公司名称', placeholder: '我的公司' },
    { key: 'escalation_intervals', label: '催办间隔 (小时)', placeholder: '24,48' },
    { key: 'report_time', label: '日报推送时间', placeholder: '09:00' },
    { key: 'token_budget_daily', label: 'Token 日预算', placeholder: '100000' },
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
    { key: 'feishu_enabled', label: '启用飞书', placeholder: 'false' },
    { key: 'feishu_boss_id', label: '老板飞书 ID', placeholder: 'ou_xxx' },
  ],
  prompt: [
    { key: 'custom_prompt', label: '自定义系统指令', type: 'textarea', placeholder: '添加自定义指令，AI 会在每次对话中遵守...' },
  ],
};

export default function Settings() {
  const [settings, setSettings] = useState<Record<string, string>>({});
  const [activeTab, setActiveTab] = useState<TabId>('general');
  const [loading, setLoading] = useState(true);
  const [savedKey, setSavedKey] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      await initSettings().catch(() => {});
      const list = await getSettings();
      const map: Record<string, string> = {};
      if (Array.isArray(list)) list.forEach((s: Setting) => { map[s.key] = s.value; });
      setSettings(map);
    } catch { /* ignore */ }
    setLoading(false);
  }, []);

  useEffect(() => { load(); }, [load]);

  const saveSetting = async (key: string) => {
    try {
      await updateSetting({ key, value: settings[key] || '' });
      setSavedKey(key);
      setTimeout(() => setSavedKey(null), 1500);
    } catch (e) { alert(String(e)); }
  };

  const saveAll = async () => {
    const fields = FIELD_DEFS[activeTab];
    for (const f of fields) {
      await updateSetting({ key: f.key, value: settings[f.key] || '' });
    }
    setSavedKey('_all');
    setTimeout(() => setSavedKey(null), 1500);
  };

  return (
    <div className="space-y-5">
      <div className="rounded-lg border border-gray-200 bg-white shadow-sm overflow-hidden">
        {/* Tab bar */}
        <div className="border-b border-gray-200 px-4 bg-gray-50/50">
          <div className="flex gap-0">
            {TABS.map((tab) => (
              <button key={tab.id} onClick={() => setActiveTab(tab.id)}
                className={`px-4 py-3 text-sm font-medium border-b-2 transition-colors ${
                  activeTab === tab.id
                    ? 'border-brand-500 text-brand-700'
                    : 'border-transparent text-gray-500 hover:text-gray-700'
                }`}>
                {tab.label}
              </button>
            ))}
          </div>
        </div>

        {/* Content */}
        <div className="p-5">
          {loading ? (
            <div className="text-center py-8 text-gray-400">加载中...</div>
          ) : (
            <div className="space-y-5 max-w-xl">
              {FIELD_DEFS[activeTab].map((field) => (
                <div key={field.key}>
                  <label className="block text-sm font-medium text-gray-600 mb-1">{field.label}</label>
                  <div className="flex gap-2">
                    {field.type === 'textarea' ? (
                      <textarea
                        value={settings[field.key] || ''}
                        onChange={(e) => setSettings({...settings, [field.key]: e.target.value})}
                        placeholder={field.placeholder}
                        rows={6}
                        className="flex-1 rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-brand-500 focus:ring-1 focus:ring-brand-500 outline-none"
                      />
                    ) : (
                      <input
                        type={field.type || 'text'}
                        value={settings[field.key] || ''}
                        onChange={(e) => setSettings({...settings, [field.key]: e.target.value})}
                        placeholder={field.placeholder}
                        className="flex-1 rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-brand-500 focus:ring-1 focus:ring-brand-500 outline-none"
                      />
                    )}
                    <button onClick={() => saveSetting(field.key)}
                      className="px-3 py-1.5 text-sm border border-gray-300 rounded-md text-gray-600 hover:bg-gray-50 flex-shrink-0">
                      {savedKey === field.key ? <Check className="w-4 h-4 text-green-600" /> : '保存'}
                    </button>
                  </div>
                </div>
              ))}
              <div className="pt-3 border-t border-gray-100">
                <button onClick={saveAll}
                  className="px-4 py-2 text-sm bg-brand-600 text-white rounded-md hover:bg-brand-700">
                  {savedKey === '_all' ? '已保存 ✓' : '保存全部'}
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
