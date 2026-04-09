const STATUS_MAP: Record<string, { bg: string; text: string; label: string }> = {
  pending:              { bg: 'bg-[rgba(255,255,255,0.06)]', text: 'text-txt-3',          label: '待处理' },
  dispatched:           { bg: 'bg-accent/10',                text: 'text-accent-light',    label: '已派发' },
  in_progress:          { bg: 'bg-amber-500/10',             text: 'text-amber-400',       label: '进行中' },
  overdue:              { bg: 'bg-red-500/10',               text: 'text-red-400',         label: '已逾期' },
  feedback_submitted:   { bg: 'bg-purple-500/10',            text: 'text-purple-400',      label: '已反馈' },
  done:                 { bg: 'bg-emerald/10',               text: 'text-emerald',         label: '已完成' },
  active:               { bg: 'bg-accent/10',                text: 'text-accent-light',    label: '进行中' },
  completed:            { bg: 'bg-emerald/10',               text: 'text-emerald',         label: '已完成' },
  approved:             { bg: 'bg-emerald/10',               text: 'text-emerald',         label: '已通过' },
  rejected:             { bg: 'bg-red-500/10',               text: 'text-red-400',         label: '已驳回' },
  normal:               { bg: 'bg-[rgba(255,255,255,0.06)]', text: 'text-txt-3',          label: '普通' },
  high:                 { bg: 'bg-amber-500/10',             text: 'text-amber-400',       label: '高' },
  urgent:               { bg: 'bg-red-500/10',               text: 'text-red-400',         label: '紧急' },
  company:              { bg: 'bg-accent/10',                text: 'text-accent-light',    label: '公司级' },
  department:           { bg: 'bg-purple-500/10',            text: 'text-purple-400',      label: '部门级' },
  individual:           { bg: 'bg-[rgba(255,255,255,0.06)]', text: 'text-txt-3',          label: '个人级' },
  sop:                  { bg: 'bg-accent/10',                text: 'text-accent-light',    label: 'SOP' },
  case:                 { bg: 'bg-emerald/10',               text: 'text-emerald',         label: '案例' },
  rule:                 { bg: 'bg-amber-500/10',             text: 'text-amber-400',       label: '规则' },
  taboo:                { bg: 'bg-red-500/10',               text: 'text-red-400',         label: '禁忌' },
  A:                    { bg: 'bg-emerald/10',               text: 'text-emerald',         label: 'A' },
  B:                    { bg: 'bg-accent/10',                text: 'text-accent-light',    label: 'B' },
  C:                    { bg: 'bg-amber-500/10',             text: 'text-amber-400',       label: 'C' },
  D:                    { bg: 'bg-red-500/10',               text: 'text-red-400',         label: 'D' },
};

interface StatusBadgeProps {
  status: string;
  customLabel?: string;
}

export default function StatusBadge({ status, customLabel }: StatusBadgeProps) {
  const cfg = STATUS_MAP[status] || { bg: 'bg-[rgba(255,255,255,0.06)]', text: 'text-txt-3', label: status };
  return (
    <span className={`inline-flex items-center px-1.5 py-0.5 rounded-micro text-[11px] font-medium ${cfg.bg} ${cfg.text}`}>
      {customLabel || cfg.label}
    </span>
  );
}
