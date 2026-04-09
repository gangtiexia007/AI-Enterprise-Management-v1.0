import { ReactNode } from 'react';
import { Link } from 'react-router-dom';

interface StatCardProps {
  label: string;
  value: string | number;
  subtitle?: string;
  icon?: ReactNode;
  borderColor?: string;
  valueColor?: string;
  iconBg?: string;
  href?: string;
  progress?: number;
  progressColor?: string;
}

export default function StatCard({
  label, value, subtitle, icon, borderColor = 'border-l-blue-500',
  valueColor = 'text-gray-900', iconBg = 'bg-blue-50 text-blue-600',
  href, progress, progressColor = 'bg-brand-500',
}: StatCardProps) {
  const content = (
    <div className={`group rounded-lg border border-gray-200 bg-white pl-4 pr-3 py-4 shadow-sm border-l-4 ${borderColor} hover:shadow-md transition-shadow`}>
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0 flex-1">
          <div className="text-xs text-gray-500 font-medium mb-1">{label}</div>
          <div className={`text-2xl font-bold ${valueColor}`}>{value}</div>
          {progress !== undefined && (
            <div className="mt-2 h-2 w-full rounded-full bg-gray-100 overflow-hidden">
              <div className={`h-full rounded-full ${progressColor} transition-all`}
                style={{ width: `${Math.min(progress, 100)}%` }} />
            </div>
          )}
        </div>
        {icon && (
          <span className={`rounded-lg p-2 flex-shrink-0 ${iconBg} group-hover:opacity-90`}>
            {icon}
          </span>
        )}
      </div>
      {subtitle && <div className="text-xs text-gray-400 mt-2">{subtitle}</div>}
    </div>
  );

  if (href) return <Link to={href}>{content}</Link>;
  return content;
}
