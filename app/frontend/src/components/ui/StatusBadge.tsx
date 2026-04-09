const STATUS_MAP: Record<string, { bg: string; text: string; label: string }> = {
  pending: { bg: 'bg-gray-100', text: 'text-gray-700', label: '待处理' },
  dispatched: { bg: 'bg-blue-100', text: 'text-blue-700', label: '已派发' },
  in_progress: { bg: 'bg-amber-100', text: 'text-amber-700', label: '进行中' },
  overdue: { bg: 'bg-red-100', text: 'text-red-700', label: '已逾期' },
  feedback_submitted: { bg: 'bg-purple-100', text: 'text-purple-700', label: '已反馈' },
  done: { bg: 'bg-green-100', text: 'text-green-700', label: '已完成' },
  active: { bg: 'bg-blue-100', text: 'text-blue-700', label: '进行中' },
  completed: { bg: 'bg-green-100', text: 'text-green-700', label: '已完成' },
  approved: { bg: 'bg-green-100', text: 'text-green-700', label: '已通过' },
  rejected: { bg: 'bg-red-100', text: 'text-red-700', label: '已驳回' },
  normal: { bg: 'bg-gray-100', text: 'text-gray-600', label: '普通' },
  high: { bg: 'bg-amber-100', text: 'text-amber-700', label: '高' },
  urgent: { bg: 'bg-red-100', text: 'text-red-700', label: '紧急' },
  company: { bg: 'bg-blue-100', text: 'text-blue-700', label: '公司级' },
  department: { bg: 'bg-indigo-100', text: 'text-indigo-700', label: '部门级' },
  individual: { bg: 'bg-gray-100', text: 'text-gray-600', label: '个人级' },
  sop: { bg: 'bg-blue-100', text: 'text-blue-700', label: 'SOP' },
  case: { bg: 'bg-emerald-100', text: 'text-emerald-700', label: '案例' },
  rule: { bg: 'bg-amber-100', text: 'text-amber-700', label: '规则' },
  taboo: { bg: 'bg-red-100', text: 'text-red-700', label: '禁忌' },
  A: { bg: 'bg-green-100', text: 'text-green-800', label: 'A' },
  B: { bg: 'bg-blue-100', text: 'text-blue-800', label: 'B' },
  C: { bg: 'bg-amber-100', text: 'text-amber-800', label: 'C' },
  D: { bg: 'bg-red-100', text: 'text-red-800', label: 'D' },
};

interface StatusBadgeProps {
  status: string;
  customLabel?: string;
}

export default function StatusBadge({ status, customLabel }: StatusBadgeProps) {
  const cfg = STATUS_MAP[status] || { bg: 'bg-gray-100', text: 'text-gray-600', label: status };
  return (
    <span className={`inline-flex items-center px-1.5 py-0.5 rounded text-xs font-medium ${cfg.bg} ${cfg.text}`}>
      {customLabel || cfg.label}
    </span>
  );
}
