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
  const [form, setForm] = useState({ title: '', category: 'sop' as string, content: '', source: 'manual' });
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

  const openCreate = () => { setEditingId(null); setForm({ title: '', category: 'sop', content: '', source: 'manual' }); setModalOpen(true); };
  const openEdit = (item: KnowledgeItem) => {
    setEditingId(item.id);
    setForm({ title: item.title, category: item.category || 'sop', content: item.content || '', source: item.source || 'manual' });
    setModalOpen(true);
  };

  const save = async () => {
    setSaving(true);
    try {
      if (editingId) await updateKnowledge(editingId, form);
      else await createKnowledge(form);
      setModalOpen(false);
      load();
    } catch (e) { alert(String(e)); }
    setSaving(false);
  };

  const handleDelete = async (id: number) => { if (confirm('确认删除？')) { await deleteKnowledge(id); load(); } };

  const categoryCounts = {
    sop: items.filter(i => i.category === 'sop').length,
    case: items.filter(i => i.category === 'case').length,
    rule: items.filter(i => i.category === 'rule').length,
    taboo: items.filter(i => i.category === 'taboo').length,
  };

  return (
    <div className="space-y-5">
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        {[
          { label: 'SOP 文档', value: categoryCounts.sop, color: 'border-l-blue-500' },
          { label: '案例', value: categoryCounts.case, color: 'border-l-emerald-500' },
          { label: '规则', value: categoryCounts.rule, color: 'border-l-amber-400' },
          { label: '禁忌', value: categoryCounts.taboo, color: 'border-l-red-500' },
        ].map(s => (
          <div key={s.label} className={`rounded-lg border border-gray-200 bg-white p-3 shadow-sm border-l-4 ${s.color} text-center`}>
            <div className="text-lg font-bold text-gray-900">{s.value}</div>
            <div className="text-xs text-gray-500">{s.label}</div>
          </div>
        ))}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-4 gap-4">
        {/* Sidebar */}
        <div className="lg:col-span-1 rounded-lg border border-gray-200 bg-white shadow-sm p-4 self-start">
          <div className="text-xs font-medium text-gray-500 uppercase tracking-wide mb-2">分类</div>
          <nav className="space-y-1">
            {CATEGORIES.map((cat) => (
              <button key={cat.value} onClick={() => setCategory(cat.value)}
                className={`block w-full text-left px-3 py-1.5 rounded-md text-sm ${
                  category === cat.value ? 'bg-brand-50 text-brand-700 font-medium' : 'text-gray-600 hover:bg-gray-50'
                }`}>
                {cat.label}
              </button>
            ))}
          </nav>
          <hr className="my-3" />
          <button onClick={openCreate}
            className="w-full flex items-center justify-center gap-1.5 px-3 py-1.5 text-sm bg-brand-600 text-white rounded-md hover:bg-brand-700">
            <Plus className="w-4 h-4" /> 新增知识
          </button>
        </div>

        {/* Table */}
        <div className="lg:col-span-3">
          {loading ? (
            <div className="text-center py-12 text-gray-400">加载中...</div>
          ) : items.length === 0 ? (
            <div className="text-center py-16 text-gray-400">
              <BookOpen className="w-12 h-12 mx-auto mb-3 text-gray-300" />
              <div className="text-sm font-semibold text-gray-600">暂无知识条目</div>
              <div className="text-xs text-gray-400 mt-1">点击左侧按钮创建第一条知识</div>
            </div>
          ) : (
            <div className="rounded-lg border border-gray-200 bg-white shadow-sm overflow-hidden">
              <div className="overflow-x-auto">
                <table className="min-w-full text-sm">
                  <thead>
                    <tr className="border-b border-gray-200 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider bg-gray-50">
                      <th className="px-4 py-3">标题</th>
                      <th className="px-4 py-3 w-24">分类</th>
                      <th className="px-4 py-3 w-24">来源</th>
                      <th className="px-4 py-3 w-28">更新时间</th>
                      <th className="px-4 py-3 w-28 text-right">操作</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-100">
                    {items.map((item) => (
                      <tr key={item.id} className="hover:bg-gray-50/80">
                        <td className="px-4 py-3">
                          <div className="font-medium text-gray-800">{item.title}</div>
                          <div className="text-xs text-gray-400 truncate max-w-sm">{item.content?.slice(0, 80)}</div>
                        </td>
                        <td className="px-4 py-3"><StatusBadge status={item.category || 'sop'} /></td>
                        <td className="px-4 py-3 text-gray-500 text-xs">{item.source || 'manual'}</td>
                        <td className="px-4 py-3 text-gray-500 text-xs">{item.updated_at?.slice(0, 10)}</td>
                        <td className="px-4 py-3 text-right">
                          <div className="flex items-center justify-end gap-2">
                            <button onClick={() => setViewItem(item)} className="text-xs text-brand-600 hover:text-brand-800"><Eye className="w-3.5 h-3.5" /></button>
                            <button onClick={() => openEdit(item)} className="text-xs text-gray-500 hover:text-gray-700">编辑</button>
                            <button onClick={() => handleDelete(item.id)} className="text-xs text-red-500 hover:text-red-700">删除</button>
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

      {/* View Modal */}
      <Modal open={!!viewItem} onClose={() => setViewItem(null)} title={viewItem?.title || ''} width="max-w-lg">
        <div className="space-y-3">
          <div className="flex items-center gap-2">
            <StatusBadge status={viewItem?.category || 'sop'} />
            <span className="text-xs text-gray-400">来源: {viewItem?.source}</span>
          </div>
          <div className="text-sm text-gray-700 whitespace-pre-wrap leading-relaxed">{viewItem?.content}</div>
        </div>
      </Modal>

      {/* Create/Edit Modal */}
      <Modal open={modalOpen} onClose={() => setModalOpen(false)} title={editingId ? '编辑知识' : '新增知识'}
        footer={<>
          <button onClick={() => setModalOpen(false)} className="px-3 py-1.5 text-sm border border-gray-300 rounded-md text-gray-600 hover:bg-gray-50">取消</button>
          <button onClick={save} disabled={saving || !form.title} className="px-3 py-1.5 text-sm bg-brand-600 text-white rounded-md hover:bg-brand-700 disabled:opacity-50">{saving ? '保存中...' : '保存'}</button>
        </>}>
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-600 mb-1">标题 <span className="text-red-500">*</span></label>
            <input value={form.title} onChange={e => setForm({...form, title: e.target.value})}
              className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-brand-500 focus:ring-1 focus:ring-brand-500 outline-none" />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-sm font-medium text-gray-600 mb-1">分类</label>
              <select value={form.category} onChange={e => setForm({...form, category: e.target.value})}
                className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-brand-500 focus:ring-1 focus:ring-brand-500 outline-none">
                <option value="sop">SOP</option>
                <option value="case">案例</option>
                <option value="rule">规则</option>
                <option value="taboo">禁忌</option>
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-600 mb-1">来源</label>
              <input value={form.source} onChange={e => setForm({...form, source: e.target.value})}
                className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-brand-500 focus:ring-1 focus:ring-brand-500 outline-none" />
            </div>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-600 mb-1">内容</label>
            <textarea value={form.content} onChange={e => setForm({...form, content: e.target.value})} rows={6}
              className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-brand-500 focus:ring-1 focus:ring-brand-500 outline-none" />
          </div>
        </div>
      </Modal>
    </div>
  );
}
