import { ReactNode } from 'react';

interface EmptyStateProps {
  icon?: ReactNode;
  title: string;
  description?: string;
  action?: ReactNode;
}

export default function EmptyState({ icon, title, description, action }: EmptyStateProps) {
  return (
    <div className="px-4 py-12 text-center">
      {icon && <div className="flex justify-center mb-3 text-gray-300">{icon}</div>}
      <div className="text-sm font-semibold text-gray-600">{title}</div>
      {description && <div className="text-xs text-gray-400 mt-1">{description}</div>}
      {action && <div className="mt-4">{action}</div>}
    </div>
  );
}
