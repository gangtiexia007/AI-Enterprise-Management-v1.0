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
      {label && <span className="text-[12px] text-txt-4 font-medium mr-1">{label}</span>}
      {options.map((opt) => (
        <button
          key={opt.value}
          onClick={() => onChange(opt.value)}
          className={`px-2.5 py-1 text-[12px] font-medium rounded-pill border transition-colors ${
            value === opt.value
              ? 'border-accent/40 bg-accent/10 text-accent-light'
              : 'border-border-solid text-txt-3 hover:text-txt-2 hover:border-border-mid'
          }`}
        >
          {opt.label}
        </button>
      ))}
    </div>
  );
}
