import { ReactNode, useState } from 'react';

interface InfoBannerProps {
  type?: 'info' | 'warning' | 'error' | 'success';
  children: ReactNode;
  dismissible?: boolean;
}

const STYLES = {
  info: 'border-blue-200 bg-blue-50 text-blue-800',
  warning: 'border-yellow-300 bg-yellow-50 text-yellow-800',
  error: 'border-red-200 bg-red-50 text-red-700',
  success: 'border-green-200 bg-green-50 text-green-800',
};

export default function InfoBanner({ type = 'info', children, dismissible }: InfoBannerProps) {
  const [visible, setVisible] = useState(true);
  if (!visible) return null;
  return (
    <div className={`rounded-lg border px-4 py-3 text-sm shadow-sm flex items-center justify-between ${STYLES[type]}`}>
      <div className="flex items-center gap-2 flex-1">{children}</div>
      {dismissible && (
        <button onClick={() => setVisible(false)} className="ml-2 opacity-60 hover:opacity-100">&times;</button>
      )}
    </div>
  );
}
