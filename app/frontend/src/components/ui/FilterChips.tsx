interface FilterOption {
  label: string;
  value: string;
}

interface FilterChipsProps {
  label?: string;
  options: FilterOption[];
  value: string;
  onChange: (value: string) => void;
}

export default function FilterChips({ label, options, value, onChange }: FilterChipsProps) {
  return (
    <div className="flex items-center gap-2 flex-wrap">
      {label && <span className="text-sm text-gray-500 font-medium mr-1">{label}</span>}
      {options.map((opt) => (
        <button
          key={opt.value}
          onClick={() => onChange(opt.value)}
          className={`px-2.5 py-1 text-xs rounded-md border transition-colors ${
            value === opt.value
              ? 'border-brand-500 bg-brand-50 text-brand-700 font-medium'
              : 'border-gray-200 text-gray-500 hover:border-gray-300 hover:text-gray-700'
          }`}
        >
          {opt.label}
        </button>
      ))}
    </div>
  );
}
