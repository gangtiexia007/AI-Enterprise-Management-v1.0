import { useEffect, useState, useCallback } from 'react';
import { BookMarked, Plus, Search, ChevronDown, ChevronUp, X, ShieldAlert, AlertTriangle, ShieldCheck, ShieldX } from 'lucide-react';
import FilterChips from '../components/ui/FilterChips';
import { getAgentMemory, createAgentMemory, type AgentMemoryItem } from '../api/client';

type ViewTab = 'review' | 'risk';

const MEMORY_TABS = [
  { label: 'SOP', value: 'sop' },
  { label: '正面案例', value: 'case_positive' },
  { label: '反面案例', value: 'case_negative' },
  { label: '平台经验', value: 'platform_insight' },
  { label: '市场经验', value: 'market_insight' },
];

const PLATFORM_FILTERS = [
  { label: '全部', value: '' },
  { label: 'Shopee', value: 'shopee' },
  { label: 'Lazada', value: 'lazada' },
  { label: 'TikTok Shop', value: 'tiktok' },
  { label: 'Etsy', value: 'etsy' },
  { label: 'Amazon', value: 'amazon' },
];

const MARKET_FILTERS = [
  { label: '全部', value: '' },
  { label: '菲律宾', value: 'PH' },
  { label: '欧美', value: 'US_EU' },
];

const RISK_TABS = [
  { label: '全部', value: '' },
  { label: '高风险表达', value: 'risk_expression' },
  { label: '平台限制', value: 'platform_restriction' },
  { label: '履约风险', value: 'fulfillment_risk' },
  { label: '待验证规则', value: 'pending_rule' },
];

const RISK_LEVEL: Record<string, { label: string; bg: string; text: string; icon: typeof ShieldAlert }> = {
  high: { label: '高风险', bg: 'bg-red-50', text: 'text-red-600', icon: ShieldX },
  medium: { label: '中风险', bg: 'bg-amber-50', text: 'text-amber-700', icon: AlertTriangle },
  low: { label: '低风险', bg: 'bg-emerald-50', text: 'text-emerald-700', icon: ShieldCheck },
};

function getRiskLevel(item: AgentMemoryItem): string {
  const text = `${item.title} ${item.action} ${item.conditions} ${item.result}`.toLowerCase();
  if (text.includes('侵权') || text.includes('禁止') || text.includes('封店') || text.includes('违规')) return 'high';
  if (text.includes('注意') || text.includes('限制') || text.includes('风险') || text.includes('审核')) return 'medium';
  return 'low';
}

const inputCls = "w-full rounded-btn border border-border bg-surface-1 px-3 py-2 text-[13px] text-txt-1 placeholder:text-txt-4 focus:border-accent/40 focus:outline-none transition-colors";

const EMPTY_FORM: Partial<AgentMemoryItem> = {
  memory_type: 'sop', title: '', platform: '', market: '', persona: '',
  niche: '', conditions: '', action: '', result: '', why: '',
};

export default function ReviewSedimentation() {
  const [viewTab, setViewTab] = useState<ViewTab>('review');

  return (
    <div className="space-y-5">
      <div className="flex gap-0 border-b border-border">
        <button onClick={() => setViewTab('review')}
          className={`flex items-center gap-2 px-4 py-3 text-[13px] font-medium border-b-2 transition-colors ${viewTab === 'review' ? 'border-accent text-accent' : 'border-transparent text-txt-4 hover:text-txt-2'}`}>
          <BookMarked className="w-4 h-4" />复盘沉淀
        </button>
        <button onClick={() => setViewTab('risk')}
          className={`flex items-center gap-2 px-4 py-3 text-[13px] font-medium border-b-2 transition-colors ${viewTab === 'risk' ? 'border-accent text-accent' : 'border-transparent text-txt-4 hover:text-txt-2'}`}>
          <ShieldAlert className="w-4 h-4" />风控中心
        </button>
      </div>
      {viewTab === 'review' && <ReviewTab />}
      {viewTab === 'risk' && <RiskTab />}
    </div>
  );
}

function ReviewTab() {
  const [items, setItems] = useState<AgentMemoryItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState('sop');
  const [platformFilter, setPlatformFilter] = useState('');
  const [marketFilter, setMarketFilter] = useState('');
  const [searchText, setSearchText] = useState('');
  const [expandedId, setExpandedId] = useState<number | null>(null);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState(EMPTY_FORM);
  const [saving, setSaving] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const params: { memory_type?: string; platform?: string; market?: string } = { memory_type: activeTab };
      if (platformFilter) params.platform = platformFilter;
      if (marketFilter) params.market = marketFilter;
      const data = await getAgentMemory(params) as unknown as { total: number; items: AgentMemoryItem[] } | AgentMemoryItem[];
      setItems(Array.isArray(data) ? data : (data as { items: AgentMemoryItem[] })?.items || []);
    } catch { setItems([]); }
    setLoading(false);
  }, [activeTab, platformFilter, marketFilter]);

  useEffect(() => { load(); }, [load]);

  const filtered = searchText
    ? items.filter(it => it.title?.includes(searchText) || it.action?.includes(searchText) || it.niche?.includes(searchText))
    : items;

  const handleSave = async () => {
    if (!form.title) return;
    setSaving(true);
    try {
      await createAgentMemory({ ...form, memory_type: activeTab });
      setShowForm(false);
      setForm(EMPTY_FORM);
      load();
    } catch (e) { alert(e instanceof Error ? e.message : '保存失败'); }
    setSaving(false);
  };

  return (
    <div className="space-y-5">
      <div className="flex items-center gap-2 flex-wrap">
        {MEMORY_TABS.map(tab => (
          <button
            key={tab.value}
            onClick={() => { setActiveTab(tab.value); setExpandedId(null); }}
            className={`px-3 py-1.5 text-[13px] font-medium rounded-btn transition-colors ${
              activeTab === tab.value ? 'bg-accent text-white' : 'bg-surface-1 border border-border text-txt-3 hover:bg-surface-3'
            }`}
          >{tab.label}</button>
        ))}
      </div>

      <div className="flex items-center justify-between gap-3 flex-wrap">
        <div className="flex items-center gap-3 flex-wrap">
          <FilterChips label="平台" options={PLATFORM_FILTERS} value={platformFilter} onChange={setPlatformFilter} />
          <FilterChips label="市场" options={MARKET_FILTERS} value={marketFilter} onChange={setMarketFilter} />
        </div>
        <div className="flex items-center gap-2">
          <div className="relative">
            <Search className="w-3.5 h-3.5 absolute left-2.5 top-1/2 -translate-y-1/2 text-txt-4" />
            <input
              value={searchText}
              onChange={e => setSearchText(e.target.value)}
              placeholder="搜索..."
              className="rounded-btn border border-border bg-surface-1 pl-8 pr-3 py-1.5 text-[13px] text-txt-1 placeholder:text-txt-4 focus:border-accent/40 focus:outline-none transition-colors w-48"
            />
          </div>
          <button
            onClick={() => { setShowForm(true); setForm({ ...EMPTY_FORM, memory_type: activeTab }); }}
            className="flex items-center gap-1.5 px-3 py-1.5 text-[13px] font-medium bg-accent text-white rounded-btn hover:bg-accent-hover transition-colors"
          >
            <Plus className="w-3.5 h-3.5" />新增
          </button>
        </div>
      </div>

      {showForm && (
        <div className="rounded-card border border-accent/30 bg-surface-1 p-4">
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-[13px] font-semibold text-txt-1">新增经验条目</h3>
            <button onClick={() => setShowForm(false)} className="text-txt-4 hover:text-txt-2"><X className="w-4 h-4" /></button>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
            <div><label className="block text-[12px] font-medium text-txt-3 mb-1">标题 <span className="text-red-500">*</span></label><input value={form.title || ''} onChange={e => setForm({ ...form, title: e.target.value })} className={inputCls} /></div>
            <div><label className="block text-[12px] font-medium text-txt-3 mb-1">平台</label><input value={form.platform || ''} onChange={e => setForm({ ...form, platform: e.target.value })} placeholder="shopee / lazada / tiktok" className={inputCls} /></div>
            <div><label className="block text-[12px] font-medium text-txt-3 mb-1">市场</label><input value={form.market || ''} onChange={e => setForm({ ...form, market: e.target.value })} placeholder="PH / US_EU" className={inputCls} /></div>
            <div><label className="block text-[12px] font-medium text-txt-3 mb-1">人设</label><input value={form.persona || ''} onChange={e => setForm({ ...form, persona: e.target.value })} className={inputCls} /></div>
            <div><label className="block text-[12px] font-medium text-txt-3 mb-1">赛道</label><input value={form.niche || ''} onChange={e => setForm({ ...form, niche: e.target.value })} className={inputCls} /></div>
            <div><label className="block text-[12px] font-medium text-txt-3 mb-1">条件</label><input value={form.conditions || ''} onChange={e => setForm({ ...form, conditions: e.target.value })} className={inputCls} /></div>
            <div className="sm:col-span-2 lg:col-span-3"><label className="block text-[12px] font-medium text-txt-3 mb-1">行动</label><textarea value={form.action || ''} onChange={e => setForm({ ...form, action: e.target.value })} rows={2} className={inputCls} /></div>
            <div className="sm:col-span-2 lg:col-span-3"><label className="block text-[12px] font-medium text-txt-3 mb-1">结果</label><textarea value={form.result || ''} onChange={e => setForm({ ...form, result: e.target.value })} rows={2} className={inputCls} /></div>
            <div className="sm:col-span-2 lg:col-span-3"><label className="block text-[12px] font-medium text-txt-3 mb-1">原因分析</label><textarea value={form.why || ''} onChange={e => setForm({ ...form, why: e.target.value })} rows={2} className={inputCls} /></div>
          </div>
          <div className="mt-3 flex justify-end gap-2">
            <button onClick={() => setShowForm(false)} className="px-3 py-1.5 text-[13px] border border-border rounded-btn text-txt-3 hover:bg-surface-3 transition-colors">取消</button>
            <button onClick={handleSave} disabled={saving || !form.title} className="px-3 py-1.5 text-[13px] bg-accent text-white rounded-btn hover:bg-accent-hover disabled:opacity-40 transition-colors">{saving ? '保存中...' : '保存'}</button>
          </div>
        </div>
      )}

      {loading ? (
        <div className="text-center py-12 text-txt-4 text-[13px]">加载中...</div>
      ) : (
        <div className="rounded-card border border-border bg-surface-1 overflow-hidden">
          <div className="border-b border-border-subtle px-4 py-3 flex items-center gap-2">
            <BookMarked className="w-4 h-4 text-txt-3" />
            <h3 className="text-[13px] font-semibold text-txt-1">
              {MEMORY_TABS.find(t => t.value === activeTab)?.label}
              <span className="text-txt-4 font-normal ml-2">{filtered.length} 条</span>
            </h3>
          </div>
          <div className="divide-y divide-border-subtle">
            {filtered.length > 0 ? filtered.map(it => (
              <div key={it.id} className="hover:bg-surface-3/40 transition-colors">
                <div
                  className="px-4 py-3 cursor-pointer flex items-center justify-between"
                  onClick={() => setExpandedId(expandedId === it.id ? null : it.id)}
                >
                  <div className="min-w-0 flex-1">
                    <div className="text-[13px] font-medium text-txt-1">{it.title}</div>
                    <div className="mt-1 flex items-center gap-2 flex-wrap">
                      {it.platform && <span className="inline-block px-1.5 py-0.5 text-[10px] rounded-micro bg-blue-50 text-blue-600">{it.platform}</span>}
                      {it.market && <span className="inline-block px-1.5 py-0.5 text-[10px] rounded-micro bg-purple-50 text-purple-600">{it.market}</span>}
                      {it.niche && <span className="inline-block px-1.5 py-0.5 text-[10px] rounded-micro bg-surface-3 text-txt-3">{it.niche}</span>}
                      <span className="text-[11px] text-txt-4">{it.created_at?.slice(0, 10)}</span>
                    </div>
                  </div>
                  {expandedId === it.id ? <ChevronUp className="w-4 h-4 text-txt-4" /> : <ChevronDown className="w-4 h-4 text-txt-4" />}
                </div>
                {expandedId === it.id && (
                  <div className="px-4 pb-4 grid grid-cols-1 sm:grid-cols-2 gap-3">
                    {[
                      { label: '人设', value: it.persona },
                      { label: '条件', value: it.conditions },
                      { label: '行动', value: it.action },
                      { label: '结果', value: it.result },
                      { label: '原因分析', value: it.why },
                      { label: '来源 Run', value: it.source_run_id },
                    ].filter(f => f.value).map(f => (
                      <div key={f.label} className="rounded-btn bg-surface-0 p-3">
                        <div className="text-[11px] font-medium text-txt-4 mb-1">{f.label}</div>
                        <div className="text-[13px] text-txt-2 whitespace-pre-wrap">{f.value}</div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )) : (
              <div className="px-4 py-12 text-center text-[13px] text-txt-4">暂无数据</div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

function RiskTab() {
  const [items, setItems] = useState<AgentMemoryItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState('');
  const [expandedId, setExpandedId] = useState<number | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const params: { memory_type?: string } = {};
      if (activeTab) params.memory_type = activeTab;
      else params.memory_type = 'rule';
      const data = await getAgentMemory(params) as unknown as { total: number; items: AgentMemoryItem[] } | AgentMemoryItem[];
      setItems(Array.isArray(data) ? data : (data as { items: AgentMemoryItem[] })?.items || []);
    } catch { setItems([]); }
    setLoading(false);
  }, [activeTab]);

  useEffect(() => { load(); }, [load]);

  const grouped = {
    high: items.filter(it => getRiskLevel(it) === 'high'),
    medium: items.filter(it => getRiskLevel(it) === 'medium'),
    low: items.filter(it => getRiskLevel(it) === 'low'),
  };

  return (
    <div className="space-y-5">
      <div className="grid grid-cols-3 gap-3">
        {(['high', 'medium', 'low'] as const).map(level => {
          const cfg = RISK_LEVEL[level];
          const Icon = cfg.icon;
          return (
            <div key={level} className="rounded-card border border-border bg-surface-1 p-4">
              <div className="flex items-start justify-between">
                <div>
                  <div className="text-[12px] font-medium text-txt-3 mb-1.5">{cfg.label}</div>
                  <div className={`text-2xl font-semibold tracking-tight ${cfg.text}`}>{grouped[level].length}</div>
                </div>
                <span className={`rounded-card p-2 ${cfg.bg} ${cfg.text}`}>
                  <Icon className="w-4 h-4" />
                </span>
              </div>
            </div>
          );
        })}
      </div>

      <FilterChips label="类型" options={RISK_TABS} value={activeTab} onChange={setActiveTab} />

      {loading ? (
        <div className="text-center py-12 text-txt-4 text-[13px]">加载中...</div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-3">
          {items.length > 0 ? items.map(it => {
            const level = getRiskLevel(it);
            const cfg = RISK_LEVEL[level];
            const Icon = cfg.icon;
            const isExpanded = expandedId === it.id;
            return (
              <div key={it.id} className={`rounded-card border bg-surface-1 overflow-hidden ${level === 'high' ? 'border-red-200' : level === 'medium' ? 'border-amber-200' : 'border-border'}`}>
                <div className="p-4">
                  <div className="flex items-start gap-2">
                    <span className={`flex-shrink-0 rounded-micro p-1.5 ${cfg.bg}`}>
                      <Icon className={`w-3.5 h-3.5 ${cfg.text}`} />
                    </span>
                    <div className="min-w-0 flex-1">
                      <div className="text-[13px] font-medium text-txt-1">{it.title}</div>
                      <div className="mt-1 flex items-center gap-2 flex-wrap">
                        <span className={`inline-flex items-center px-1.5 py-0.5 rounded-micro text-[11px] font-medium ${cfg.bg} ${cfg.text}`}>{cfg.label}</span>
                        {it.platform && <span className="inline-block px-1.5 py-0.5 text-[10px] rounded-micro bg-blue-50 text-blue-600">{it.platform}</span>}
                        {it.market && <span className="inline-block px-1.5 py-0.5 text-[10px] rounded-micro bg-purple-50 text-purple-600">{it.market}</span>}
                      </div>
                    </div>
                  </div>
                  {it.action && (
                    <div className="mt-2 text-[12px] text-txt-3 line-clamp-2">{it.action}</div>
                  )}
                  <button
                    onClick={() => setExpandedId(isExpanded ? null : it.id)}
                    className="mt-2 text-[11px] text-accent hover:text-accent-hover transition-colors"
                  >
                    {isExpanded ? '收起' : '查看详情'}
                  </button>
                </div>
                {isExpanded && (
                  <div className="border-t border-border-subtle px-4 py-3 bg-surface-0/50 space-y-2">
                    {it.conditions && (
                      <div>
                        <div className="text-[11px] font-medium text-txt-4">触发条件</div>
                        <div className="text-[12px] text-txt-2 mt-0.5">{it.conditions}</div>
                      </div>
                    )}
                    {it.result && (
                      <div>
                        <div className="text-[11px] font-medium text-txt-4">后果/结果</div>
                        <div className="text-[12px] text-txt-2 mt-0.5">{it.result}</div>
                      </div>
                    )}
                    {it.why && (
                      <div>
                        <div className="text-[11px] font-medium text-txt-4">原因</div>
                        <div className="text-[12px] text-txt-2 mt-0.5">{it.why}</div>
                      </div>
                    )}
                    <div className="text-[11px] text-txt-4 pt-1">{it.created_at?.slice(0, 16)}</div>
                  </div>
                )}
              </div>
            );
          }) : (
            <div className="col-span-full px-4 py-12 text-center text-[13px] text-txt-4 rounded-card border border-border bg-surface-1">暂无风控数据</div>
          )}
        </div>
      )}
    </div>
  );
}
