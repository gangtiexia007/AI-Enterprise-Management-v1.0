import { ReactNode } from 'react';
import { Link } from 'react-router-dom';

interface StatCardProps {
  label: string;
  value: string | number;
  subtitle?: string;
  icon?: ReactNode;
  href?: string;
  progress?: number;
  accent?: string;
}

export default function StatCard({
  label, value, subtitle, icon, href, progress, accent,
}: StatCardProps) {
  const content = (
    <div className="group rounded-card border border-border bg-[rgba(255,255,255,0.02)] p-4 hover:bg-[rgba(255,255,255,0.04)] transition-all">
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0 flex-1">
          <div className="text-[12px] font-medium text-txt-3 mb-1.5">{label}</div>
          <div className={`text-2xl font-semibold tracking-tight ${accent || 'text-txt-1'}`}>{value}</div>
          {progress !== undefined && (
            <div className="mt-2.5 h-1 w-full rounded-full bg-[rgba(255,255,255,0.06)] overflow-hidden">
              <div className="h-full rounded-full bg-accent-light transition-all duration-500"
                style={{ width: `${Math.min(progress, 100)}%` }} />
            </div>
          )}
        </div>
        {icon && (
          <span className="rounded-card p-2 bg-[rgba(255,255,255,0.04)] text-txt-3 flex-shrink-0 group-hover:text-accent-light transition-colors">
            {icon}
          </span>
        )}
      </div>
      {subtitle && <div className="text-[11px] text-txt-4 mt-2">{subtitle}</div>}
    </div>
  );

  if (href) return <Link to={href} className="block">{content}</Link>;
  return content;
}
