const STATUS_MAP: Record<string, { bg: string; text: string; label: string }> = {
  pending:            { bg: 'bg-gray-100',     text: 'text-gray-600',    label: '待处理' },
  dispatched:         { bg: 'bg-indigo-50',    text: 'text-indigo-600',  label: '已派发' },
  in_progress:        { bg: 'bg-amber-50',     text: 'text-amber-700',   label: '进行中' },
  overdue:            { bg: 'bg-red-50',       text: 'text-red-600',     label: '已逾期' },
  feedback_submitted: { bg: 'bg-purple-50',    text: 'text-purple-600',  label: '已反馈' },
  done:               { bg: 'bg-emerald-50',   text: 'text-emerald-700', label: '已完成' },
  active:             { bg: 'bg-blue-50',      text: 'text-blue-600',    label: '进行中' },
  completed:          { bg: 'bg-emerald-50',   text: 'text-emerald-700', label: '已完成' },
  approved:           { bg: 'bg-emerald-50',   text: 'text-emerald-700', label: '已通过' },
  rejected:           { bg: 'bg-red-50',       text: 'text-red-600',     label: '已驳回' },
  normal:             { bg: 'bg-gray-100',     text: 'text-gray-600',    label: '普通' },
  high:               { bg: 'bg-amber-50',     text: 'text-amber-700',   label: '高' },
  urgent:             { bg: 'bg-red-50',       text: 'text-red-600',     label: '紧急' },
  company:            { bg: 'bg-indigo-50',    text: 'text-indigo-600',  label: '公司级' },
  department:         { bg: 'bg-purple-50',    text: 'text-purple-600',  label: '部门级' },
  individual:         { bg: 'bg-gray-100',     text: 'text-gray-600',    label: '个人级' },
  sop:                { bg: 'bg-blue-50',      text: 'text-blue-600',    label: 'SOP' },
  case:               { bg: 'bg-emerald-50',   text: 'text-emerald-700', label: '案例' },
  rule:               { bg: 'bg-amber-50',     text: 'text-amber-700',   label: '规则' },
  taboo:              { bg: 'bg-red-50',       text: 'text-red-600',     label: '禁忌' },
  A:                  { bg: 'bg-emerald-50',   text: 'text-emerald-700', label: 'A' },
  B:                  { bg: 'bg-blue-50',      text: 'text-blue-600',    label: 'B' },
  C:                  { bg: 'bg-amber-50',     text: 'text-amber-700',   label: 'C' },
  D:                  { bg: 'bg-red-50',       text: 'text-red-600',     label: 'D' },
};

export default function StatusBadge({ status, customLabel }: { status: string; customLabel?: string }) {
  const cfg = STATUS_MAP[status] || { bg: 'bg-gray-100', text: 'text-gray-600', label: status };
  return (
    <span className={`inline-flex items-center px-1.5 py-0.5 rounded-micro text-[11px] font-medium ${cfg.bg} ${cfg.text}`}>
      {customLabel || cfg.label}
    </span>
  );
}
