import { useEffect, useState, useCallback } from 'react';
import { Search, Send, History, ChevronDown, ChevronUp, TrendingDown, AlertCircle } from 'lucide-react';
import { multiAgentChat, getMultiAgentRuns, type MultiAgentRun } from '../api/client';

type AnalysisTab = 'niche' | 'attribution';

const MARKETS = [
  { label: '菲律宾', value: 'PH' },
  { label: '欧美', value: 'US_EU' },
];
const PLATFORMS = [
  { label: 'Shopee', value: 'shopee' },
  { label: 'Lazada', value: 'lazada' },
  { label: 'TikTok Shop', value: 'tiktok' },
  { label: 'Etsy', value: 'etsy' },
  { label: 'Amazon', value: 'amazon' },
];

const EVAL_DIMENSIONS = [
  '市场容量', '竞争强度', '利润空间', 'POD 适配度', '复购潜力',
  '季节性风险', '侵权风险', '供应链难度', '广告成本', '增长趋势',
];

const FUNNEL_LAYERS = [
  { key: 'impressions', label: '曝光', color: 'bg-blue-500' },
  { key: 'clicks', label: '点击', color: 'bg-indigo-500' },
  { key: 'conversion', label: '转化', color: 'bg-purple-500' },
  { key: 'profit', label: '利润', color: 'bg-emerald-500' },
  { key: 'fulfillment', label: '履约', color: 'bg-amber-500' },
];

const inputCls = "w-full rounded-btn border border-border bg-surface-1 px-3 py-2 text-[13px] text-txt-1 placeholder:text-txt-4 focus:border-accent/40 focus:outline-none transition-colors";

export default function AgentAnalysis() {
  const [tab, setTab] = useState<AnalysisTab>('niche');

  return (
    <div className="space-y-5">
      <div className="flex gap-0 border-b border-border">
        <button onClick={() => setTab('niche')}
          className={`flex items-center gap-2 px-4 py-3 text-[13px] font-medium border-b-2 transition-colors ${tab === 'niche' ? 'border-accent text-accent' : 'border-transparent text-txt-4 hover:text-txt-2'}`}>
          <Search className="w-4 h-4" />赛道研究
        </button>
        <button onClick={() => setTab('attribution')}
          className={`flex items-center gap-2 px-4 py-3 text-[13px] font-medium border-b-2 transition-colors ${tab === 'attribution' ? 'border-accent text-accent' : 'border-transparent text-txt-4 hover:text-txt-2'}`}>
          <TrendingDown className="w-4 h-4" />数据归因
        </button>
      </div>
      {tab === 'niche' && <NicheTab />}
      {tab === 'attribution' && <AttributionTab />}
    </div>
  );
}

interface EvalResult {
  response: string;
  run_id: string;
  task_type: string;
}

function NicheTab() {
  const [niche, setNiche] = useState('');
  const [market, setMarket] = useState('PH');
  const [platform, setPlatform] = useState('shopee');
  const [sending, setSending] = useState(false);
  const [result, setResult] = useState<EvalResult | null>(null);
  const [history, setHistory] = useState<MultiAgentRun[]>([]);
  const [showHistory, setShowHistory] = useState(false);
  const [expandedHistory, setExpandedHistory] = useState<number | null>(null);
  const [error, setError] = useState('');

  const loadHistory = useCallback(async () => {
    try {
      const data = await getMultiAgentRuns({ limit: 50 }) as unknown as { total: number; items: MultiAgentRun[] };
      const list = Array.isArray(data) ? data : (data?.items || []);
      const filtered = list.filter(
        r => r.task_type === 'new_direction' || r.route_name?.includes('niche')
      );
      setHistory(filtered);
    } catch { setHistory([]); }
  }, []);

  useEffect(() => { loadHistory(); }, [loadHistory]);

  const handleSubmit = async () => {
    if (!niche.trim() || sending) return;
    setSending(true);
    setError('');
    setResult(null);
    try {
      const content = `请对以下 POD 赛道进行深度评估：\n赛道名称: ${niche}\n目标市场: ${market}\n目标平台: ${platform}\n\n请从十个维度进行评分（1-10分），并给出最终判断（值得做/可测试/跳过）和 micro-niche 细分建议。`;
      const res = await multiAgentChat(content, { niche, market, platform });
      setResult(res);
      loadHistory();
    } catch (e) {
      setError(e instanceof Error ? e.message : '请求失败');
    }
    setSending(false);
  };

  const tryParseScores = (text: string): Record<string, number> => {
    const scores: Record<string, number> = {};
    for (const dim of EVAL_DIMENSIONS) {
      const regex = new RegExp(`${dim}[：:\\s]*([0-9]+)`, 'i');
      const m = text.match(regex);
      if (m) scores[dim] = parseInt(m[1], 10);
    }
    return scores;
  };

  const scores = result ? tryParseScores(result.response) : {};
  const hasScores = Object.keys(scores).length > 0;

  return (
    <div className="space-y-5">
      <div className="rounded-card border border-border bg-surface-1 p-4">
        <div className="flex items-center gap-2 mb-4">
          <Search className="w-4 h-4 text-txt-3" />
          <h3 className="text-[13px] font-semibold text-txt-1">赛道研究</h3>
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-4 gap-3">
          <div className="sm:col-span-2">
            <label className="block text-[12px] font-medium text-txt-3 mb-1.5">赛道名称</label>
            <input
              value={niche}
              onChange={e => setNiche(e.target.value)}
              placeholder="例如：宠物服饰、瑜伽周边、汽车贴纸"
              className={inputCls}
            />
          </div>
          <div>
            <label className="block text-[12px] font-medium text-txt-3 mb-1.5">目标市场</label>
            <select value={market} onChange={e => setMarket(e.target.value)} className={inputCls}>
              {MARKETS.map(m => <option key={m.value} value={m.value}>{m.label}</option>)}
            </select>
          </div>
          <div>
            <label className="block text-[12px] font-medium text-txt-3 mb-1.5">目标平台</label>
            <select value={platform} onChange={e => setPlatform(e.target.value)} className={inputCls}>
              {PLATFORMS.map(p => <option key={p.value} value={p.value}>{p.label}</option>)}
            </select>
          </div>
        </div>
        <div className="mt-4 flex justify-end">
          <button
            onClick={handleSubmit}
            disabled={sending || !niche.trim()}
            className="flex items-center gap-1.5 px-4 py-2 text-[13px] font-medium bg-accent text-white rounded-btn hover:bg-accent-hover disabled:opacity-40 transition-colors"
          >
            <Send className="w-3.5 h-3.5" />
            {sending ? '分析中...' : '开始评估'}
          </button>
        </div>
      </div>

      {error && (
        <div className="rounded-card border border-red-200 bg-red-50 p-4 text-[13px] text-red-600">{error}</div>
      )}

      {result && (
        <div className="rounded-card border border-border bg-surface-1 overflow-hidden">
          <div className="border-b border-border-subtle px-4 py-3 flex items-center justify-between">
            <h3 className="text-[13px] font-semibold text-txt-1">评估结果</h3>
            <div className="flex items-center gap-2">
              {result.task_type && (
                <span className="inline-block px-2 py-0.5 text-[11px] rounded-full bg-indigo-50 text-indigo-700">{result.task_type}</span>
              )}
            </div>
          </div>

          {hasScores && (
            <div className="px-4 py-3 border-b border-border-subtle">
              <div className="text-[12px] font-medium text-txt-3 mb-2">十维评分</div>
              <div className="grid grid-cols-2 sm:grid-cols-5 gap-2">
                {EVAL_DIMENSIONS.map(dim => {
                  const score = scores[dim];
                  const color = score != null
                    ? score >= 7 ? 'text-emerald-700 bg-emerald-50' : score >= 4 ? 'text-amber-700 bg-amber-50' : 'text-red-600 bg-red-50'
                    : 'text-txt-4 bg-surface-3';
                  return (
                    <div key={dim} className="flex items-center justify-between gap-2 px-2 py-1.5 rounded-btn bg-surface-0">
                      <span className="text-[11px] text-txt-3 truncate">{dim}</span>
                      <span className={`inline-flex items-center justify-center h-5 min-w-[20px] px-1 rounded-micro text-[11px] font-bold ${color}`}>
                        {score ?? '-'}
                      </span>
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          <div className="px-4 py-3">
            <div className="text-[13px] text-txt-2 whitespace-pre-wrap">{result.response}</div>
          </div>
        </div>
      )}

      <div className="rounded-card border border-border bg-surface-1 overflow-hidden">
        <button
          onClick={() => setShowHistory(!showHistory)}
          className="w-full px-4 py-3 flex items-center justify-between hover:bg-surface-3/40 transition-colors"
        >
          <div className="flex items-center gap-2">
            <History className="w-4 h-4 text-txt-3" />
            <h3 className="text-[13px] font-semibold text-txt-1">历史评估记录</h3>
            <span className="text-[11px] text-txt-4">{history.length} 条</span>
          </div>
          {showHistory ? <ChevronUp className="w-4 h-4 text-txt-4" /> : <ChevronDown className="w-4 h-4 text-txt-4" />}
        </button>
        {showHistory && (
          <div className="border-t border-border-subtle divide-y divide-border-subtle">
            {history.length > 0 ? history.map(r => (
              <div key={r.id} className="px-4 py-3 hover:bg-surface-3/40 transition-colors">
                <div
                  className="flex items-center justify-between cursor-pointer"
                  onClick={() => setExpandedHistory(expandedHistory === r.id ? null : r.id)}
                >
                  <div>
                    <span className="text-[13px] font-medium text-txt-1">{r.input_summary || r.route_name}</span>
                    <span className="text-[11px] text-txt-4 ml-2">{r.created_at?.slice(0, 16)}</span>
                  </div>
                  <span className={`inline-flex items-center px-1.5 py-0.5 rounded-micro text-[11px] font-medium ${
                    r.data_sufficiency === 'sufficient' ? 'bg-emerald-50 text-emerald-700' : 'bg-amber-50 text-amber-700'
                  }`}>{r.data_sufficiency || '-'}</span>
                </div>
                {expandedHistory === r.id && r.final_output && (
                  <div className="mt-2 p-3 bg-surface-0 rounded-btn text-[12px] text-txt-3 whitespace-pre-wrap max-h-48 overflow-y-auto">
                    {r.final_output}
                  </div>
                )}
              </div>
            )) : (
              <div className="px-4 py-8 text-center text-[13px] text-txt-4">暂无历史记录</div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

interface FunnelData {
  impressions: string;
  clicks: string;
  ctr: string;
  conversion: string;
  orders: string;
  revenue: string;
  cost: string;
}

const EMPTY_FUNNEL: FunnelData = {
  impressions: '', clicks: '', ctr: '', conversion: '', orders: '', revenue: '', cost: '',
};

function AttributionTab() {
  const [storeName, setStoreName] = useState('');
  const [funnel, setFunnel] = useState<FunnelData>(EMPTY_FUNNEL);
  const [sending, setSending] = useState(false);
  const [result, setResult] = useState<{ response: string; problemLayer: string } | null>(null);
  const [error, setError] = useState('');

  const handleAnalyze = async () => {
    setSending(true);
    setError('');
    setResult(null);
    try {
      const content = `请对以下店铺/产品数据进行五层归因分析：
店铺: ${storeName || '未指定'}
曝光: ${funnel.impressions || '无'}
点击: ${funnel.clicks || '无'}
CTR: ${funnel.ctr || '无'}
转化率: ${funnel.conversion || '无'}
订单数: ${funnel.orders || '无'}
收入: ${funnel.revenue || '无'}
成本: ${funnel.cost || '无'}

请判断问题出在哪一层（曝光/点击/转化/利润/履约），并给出改进建议。`;

      const res = await multiAgentChat(content, { store_id: storeName, data: funnel });
      const text = res.response.toLowerCase();
      let problemLayer = '';
      if (text.includes('曝光') && (text.includes('问题') || text.includes('不足'))) problemLayer = 'impressions';
      else if (text.includes('点击') && (text.includes('问题') || text.includes('偏低'))) problemLayer = 'clicks';
      else if (text.includes('转化') && (text.includes('问题') || text.includes('偏低'))) problemLayer = 'conversion';
      else if (text.includes('利润') && (text.includes('问题') || text.includes('亏损'))) problemLayer = 'profit';
      else if (text.includes('履约') && (text.includes('问题') || text.includes('延迟'))) problemLayer = 'fulfillment';

      setResult({ response: res.response, problemLayer });
    } catch (e) {
      setError(e instanceof Error ? e.message : '分析请求失败');
    }
    setSending(false);
  };

  const funnelValues = [
    parseFloat(funnel.impressions) || 0,
    parseFloat(funnel.clicks) || 0,
    parseFloat(funnel.orders) || 0,
    parseFloat(funnel.revenue) || 0,
    parseFloat(funnel.cost) || 0,
  ];
  const maxVal = Math.max(...funnelValues, 1);

  return (
    <div className="space-y-5">
      <div className="rounded-card border border-border bg-surface-1 p-4">
        <div className="flex items-center gap-2 mb-4">
          <TrendingDown className="w-4 h-4 text-txt-3" />
          <h3 className="text-[13px] font-semibold text-txt-1">数据归因分析</h3>
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
          <div className="sm:col-span-2 lg:col-span-4">
            <label className="block text-[12px] font-medium text-txt-3 mb-1.5">店铺/产品名称</label>
            <input value={storeName} onChange={e => setStoreName(e.target.value)} placeholder="输入店铺或产品名称" className={inputCls} />
          </div>
          <div>
            <label className="block text-[12px] font-medium text-txt-3 mb-1.5">曝光量</label>
            <input value={funnel.impressions} onChange={e => setFunnel({ ...funnel, impressions: e.target.value })} placeholder="例如: 15000" className={inputCls} />
          </div>
          <div>
            <label className="block text-[12px] font-medium text-txt-3 mb-1.5">点击量</label>
            <input value={funnel.clicks} onChange={e => setFunnel({ ...funnel, clicks: e.target.value })} placeholder="例如: 450" className={inputCls} />
          </div>
          <div>
            <label className="block text-[12px] font-medium text-txt-3 mb-1.5">CTR (%)</label>
            <input value={funnel.ctr} onChange={e => setFunnel({ ...funnel, ctr: e.target.value })} placeholder="例如: 3.0" className={inputCls} />
          </div>
          <div>
            <label className="block text-[12px] font-medium text-txt-3 mb-1.5">转化率 (%)</label>
            <input value={funnel.conversion} onChange={e => setFunnel({ ...funnel, conversion: e.target.value })} placeholder="例如: 2.5" className={inputCls} />
          </div>
          <div>
            <label className="block text-[12px] font-medium text-txt-3 mb-1.5">订单数</label>
            <input value={funnel.orders} onChange={e => setFunnel({ ...funnel, orders: e.target.value })} placeholder="例如: 12" className={inputCls} />
          </div>
          <div>
            <label className="block text-[12px] font-medium text-txt-3 mb-1.5">收入</label>
            <input value={funnel.revenue} onChange={e => setFunnel({ ...funnel, revenue: e.target.value })} placeholder="例如: 3600" className={inputCls} />
          </div>
          <div>
            <label className="block text-[12px] font-medium text-txt-3 mb-1.5">成本</label>
            <input value={funnel.cost} onChange={e => setFunnel({ ...funnel, cost: e.target.value })} placeholder="例如: 2800" className={inputCls} />
          </div>
        </div>
        <div className="mt-4 flex justify-end">
          <button
            onClick={handleAnalyze}
            disabled={sending}
            className="flex items-center gap-1.5 px-4 py-2 text-[13px] font-medium bg-accent text-white rounded-btn hover:bg-accent-hover disabled:opacity-40 transition-colors"
          >
            <Send className="w-3.5 h-3.5" />
            {sending ? '分析中...' : '开始归因'}
          </button>
        </div>
      </div>

      {funnelValues.some(v => v > 0) && (
        <div className="rounded-card border border-border bg-surface-1 p-4">
          <h3 className="text-[13px] font-semibold text-txt-1 mb-4">漏斗可视化</h3>
          <div className="space-y-3">
            {FUNNEL_LAYERS.map((layer, i) => {
              const val = funnelValues[i] || 0;
              const pct = maxVal > 0 ? Math.max((val / maxVal) * 100, 2) : 2;
              const isProblem = result?.problemLayer === layer.key;
              return (
                <div key={layer.key} className="flex items-center gap-3">
                  <span className={`text-[12px] font-medium w-12 text-right ${isProblem ? 'text-red-600' : 'text-txt-3'}`}>
                    {layer.label}
                  </span>
                  <div className="flex-1 h-8 bg-surface-3 rounded-btn overflow-hidden relative">
                    <div
                      className={`h-full rounded-btn transition-all duration-500 ${isProblem ? 'bg-red-500' : layer.color}`}
                      style={{ width: `${pct}%` }}
                    />
                    <span className="absolute inset-0 flex items-center px-3 text-[12px] font-medium text-white mix-blend-difference">
                      {val > 0 ? val.toLocaleString() : '-'}
                    </span>
                  </div>
                  {isProblem && <AlertCircle className="w-4 h-4 text-red-500 flex-shrink-0" />}
                </div>
              );
            })}
          </div>
        </div>
      )}

      {error && (
        <div className="rounded-card border border-red-200 bg-red-50 p-4 text-[13px] text-red-600">{error}</div>
      )}

      {result && (
        <div className="rounded-card border border-border bg-surface-1 overflow-hidden">
          <div className="border-b border-border-subtle px-4 py-3 flex items-center justify-between">
            <h3 className="text-[13px] font-semibold text-txt-1">归因分析结果</h3>
            {result.problemLayer && (
              <span className="inline-flex items-center px-1.5 py-0.5 rounded-micro text-[11px] font-medium bg-red-50 text-red-600">
                问题层: {FUNNEL_LAYERS.find(l => l.key === result.problemLayer)?.label || result.problemLayer}
              </span>
            )}
          </div>
          <div className="px-4 py-3">
            <div className="text-[13px] text-txt-2 whitespace-pre-wrap">{result.response}</div>
          </div>
        </div>
      )}
    </div>
  );
}
