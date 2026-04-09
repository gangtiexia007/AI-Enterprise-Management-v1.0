import { useEffect, useState, useCallback } from 'react';
import { BookOpen, Plus, Eye } from 'lucide-react';
import StatusBadge from '../components/ui/StatusBadge';
import Modal from '../components/Modal';
import { getKnowledge, createKnowledge, updateKnowledge, deleteKnowledge, type KnowledgeItem } from '../api/client';

const CATEGORIES = [
  { label: '全部', value: '' },
  { label: 'SOP', value: 'sop' },
  { label: '案例', value: 'case' },
  { label: '规则', value: 'rule' },
  { label: '禁忌', value: 'taboo' },
];

export default function Knowledge() {
  const [items, setItems] = useState<KnowledgeItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [category, setCategory] = useState('');
  const [modalOpen, setModalOpen] = useState(false);
  const [viewItem, setViewItem] = useState<KnowledgeItem | null>(null);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [form, setForm] = useState({ title: '', category: 'sop' as 'sop' | 'case' | 'rule' | 'taboo', content: '', source: 'manual' });
  const [saving, setSaving] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const params: Record<string, string> = {};
      if (category) params.category = category;
      const k = await getKnowledge(params);
      setItems(Array.isArray(k) ? k : []);
    } catch { setItems([]); }
    setLoading(false);
  }, [category]);

  useEffect(() => { load(); }, [load]);

  const openCreate = () => { setEditingId(null); setForm({ title: '', category: 'sop' as 'sop' | 'case' | 'rule' | 'taboo', content: '', source: 'manual' }); setModalOpen(true); };
  const openEdit = (item: KnowledgeItem) => {
    setEditingId(item.id);
    setForm({ title: item.title, category: item.category || 'sop', content: item.content || '', source: item.source || 'manual' });
    setModalOpen(true);
  };

  const save = async () => {
    setSaving(true);
    try { if (editingId) await updateKnowledge(editingId, form); else await createKnowledge(form); setModalOpen(false); load(); }
    catch (e) { alert(String(e)); }
    setSaving(false);
  };

  const handleDelete = async (id: number) => { if (confirm('确认删除？')) { await deleteKnowledge(id); load(); } };

  const categoryCounts = {
    sop: items.filter(i => i.category === 'sop').length,
    case: items.filter(i => i.category === 'case').length,
    rule: items.filter(i => i.category === 'rule').length,
    taboo: items.filter(i => i.category === 'taboo').length,
  };

  const inputCls = "w-full rounded-btn border border-border bg-[rgba(255,255,255,0.02)] px-3 py-2 text-[13px] text-txt-2 placeholder:text-txt-4 focus:border-accent/40 focus:outline-none transition-colors";

  return (
    <div className="space-y-5">
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        {[
          { label: 'SOP 文档', value: categoryCounts.sop },
          { label: '案例', value: categoryCounts.case },
          { label: '规则', value: categoryCounts.rule },
          { label: '禁忌', value: categoryCounts.taboo },
        ].map(s => (
          <div key={s.label} className="rounded-card border border-border bg-[rgba(255,255,255,0.02)] p-3 text-center hover:bg-[rgba(255,255,255,0.04)] transition-colors">
            <div className="text-xl font-semibold text-txt-1">{s.value}</div>
            <div className="text-[11px] text-txt-4 mt-1">{s.label}</div>
          </div>
        ))}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-4 gap-4">
        <div className="lg:col-span-1 rounded-card border border-border bg-[rgba(255,255,255,0.02)] p-4 self-start">
          <div className="text-[10px] font-medium text-txt-4 uppercase tracking-wide mb-2">分类</div>
          <nav className="space-y-0.5">
            {CATEGORIES.map((cat) => (
              <button key={cat.value} onClick={() => setCategory(cat.value)}
                className={`block w-full text-left px-3 py-1.5 rounded-btn text-[13px] transition-colors ${
                  category === cat.value ? 'bg-accent/10 text-accent-light font-medium' : 'text-txt-3 hover:bg-[rgba(255,255,255,0.03)] hover:text-txt-2'
                }`}>
                {cat.label}
              </button>
            ))}
          </nav>
          <hr className="my-3 border-border" />
          <button onClick={openCreate}
            className="w-full flex items-center justify-center gap-1.5 px-3 py-1.5 text-[13px] font-medium bg-accent text-white rounded-btn hover:bg-accent-hover transition-colors">
            <Plus className="w-3.5 h-3.5" /> 新增知识
          </button>
        </div>

        <div className="lg:col-span-3">
          {loading ? (
            <div className="text-center py-12 text-txt-4 text-[13px]">加载中...</div>
          ) : items.length === 0 ? (
            <div className="text-center py-16">
              <BookOpen className="w-10 h-10 mx-auto mb-3 text-txt-4" />
              <div className="text-[14px] font-medium text-txt-3">暂无知识条目</div>
              <div className="text-[12px] text-txt-4 mt-1">点击左侧按钮创建第一条知识</div>
            </div>
          ) : (
            <div className="rounded-card border border-border overflow-hidden">
              <div className="overflow-x-auto">
                <table className="min-w-full text-[13px]">
                  <thead>
                    <tr className="border-b border-border text-left text-[11px] font-medium text-txt-4 uppercase tracking-wider">
                      <th className="px-4 py-3">标题</th>
                      <th className="px-4 py-3 w-24">分类</th>
                      <th className="px-4 py-3 w-24">来源</th>
                      <th className="px-4 py-3 w-28">更新时间</th>
                      <th className="px-4 py-3 w-28 text-right">操作</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border">
                    {items.map((item) => (
                      <tr key={item.id} className="hover:bg-[rgba(255,255,255,0.02)] transition-colors">
                        <td className="px-4 py-3">
                          <div className="font-medium text-txt-1">{item.title}</div>
                          <div className="text-[11px] text-txt-4 truncate max-w-sm mt-0.5">{item.content?.slice(0, 80)}</div>
                        </td>
                        <td className="px-4 py-3"><StatusBadge status={item.category || 'sop'} /></td>
                        <td className="px-4 py-3 text-txt-4 text-[12px]">{item.source || 'manual'}</td>
                        <td className="px-4 py-3 text-txt-4 text-[12px]">{item.updated_at?.slice(0, 10)}</td>
                        <td className="px-4 py-3 text-right">
                          <div className="flex items-center justify-end gap-3">
                            <button onClick={() => setViewItem(item)} className="text-accent-light hover:text-accent-hover transition-colors"><Eye className="w-3.5 h-3.5" /></button>
                            <button onClick={() => openEdit(item)} className="text-[12px] text-txt-4 hover:text-txt-2 transition-colors">编辑</button>
                            <button onClick={() => handleDelete(item.id)} className="text-[12px] text-red-400/70 hover:text-red-400 transition-colors">删除</button>
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>
      </div>

      <Modal open={!!viewItem} onClose={() => setViewItem(null)} title={viewItem?.title || ''} width="max-w-lg">
        <div className="space-y-3">
          <div className="flex items-center gap-2">
            <StatusBadge status={viewItem?.category || 'sop'} />
            <span className="text-[11px] text-txt-4">来源: {viewItem?.source}</span>
          </div>
          <div className="text-[13px] text-txt-2 whitespace-pre-wrap leading-relaxed">{viewItem?.content}</div>
        </div>
      </Modal>

      <Modal open={modalOpen} onClose={() => setModalOpen(false)} title={editingId ? '编辑知识' : '新增知识'}
        footer={<>
          <button onClick={() => setModalOpen(false)} className="px-3 py-1.5 text-[13px] border border-border rounded-btn text-txt-3 hover:bg-[rgba(255,255,255,0.04)] transition-colors">取消</button>
          <button onClick={save} disabled={saving || !form.title} className="px-3 py-1.5 text-[13px] bg-accent text-white rounded-btn hover:bg-accent-hover disabled:opacity-40 transition-colors">{saving ? '保存中...' : '保存'}</button>
        </>}>
        <div className="space-y-4">
          <div>
            <label className="block text-[12px] font-medium text-txt-3 mb-1.5">标题 <span className="text-red-400">*</span></label>
            <input value={form.title} onChange={e => setForm({...form, title: e.target.value})} className={inputCls} />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-[12px] font-medium text-txt-3 mb-1.5">分类</label>
              <select value={form.category} onChange={e => setForm({...form, category: e.target.value as 'sop' | 'case' | 'rule' | 'taboo'})} className={inputCls}>
                <option value="sop">SOP</option>
                <option value="case">案例</option>
                <option value="rule">规则</option>
                <option value="taboo">禁忌</option>
              </select>
            </div>
            <div>
              <label className="block text-[12px] font-medium text-txt-3 mb-1.5">来源</label>
              <input value={form.source} onChange={e => setForm({...form, source: e.target.value})} className={inputCls} />
            </div>
          </div>
          <div>
            <label className="block text-[12px] font-medium text-txt-3 mb-1.5">内容</label>
            <textarea value={form.content} onChange={e => setForm({...form, content: e.target.value})} rows={6} className={inputCls} />
          </div>
        </div>
      </Modal>
    </div>
  );
}
