const colorMap: Record<string, string> = {
  pending: "bg-gray-100 text-gray-700",
  dispatched: "bg-blue-100 text-blue-700",
  in_progress: "bg-yellow-100 text-yellow-800",
  overdue: "bg-red-100 text-red-700",
  feedback_submitted: "bg-purple-100 text-purple-700",
  done: "bg-green-100 text-green-700",
  active: "bg-green-100 text-green-700",
  completed: "bg-green-100 text-green-700",
  sop: "bg-blue-100 text-blue-700",
  case: "bg-green-100 text-green-700",
  rule: "bg-yellow-100 text-yellow-800",
  taboo: "bg-red-100 text-red-700",
};

const labelMap: Record<string, string> = {
  pending: "待处理",
  dispatched: "已下发",
  in_progress: "进行中",
  overdue: "已逾期",
  feedback_submitted: "已反馈",
  done: "已完成",
  active: "进行中",
  completed: "已完成",
  normal: "普通",
  high: "高",
  urgent: "紧急",
  sop: "SOP",
  case: "案例",
  rule: "规则",
  taboo: "禁忌",
  company: "公司",
  department: "部门",
  individual: "个人",
};

interface BadgeProps {
  value: string;
  className?: string;
}

export function Badge({ value, className = "" }: BadgeProps) {
  const colors = colorMap[value] || "bg-gray-100 text-gray-600";
  const label = labelMap[value] || value;

  return (
    <span
      className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${colors} ${className}`}
    >
      {label}
    </span>
  );
}
