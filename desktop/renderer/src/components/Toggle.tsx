import type { LucideIcon } from "lucide-react";

export function Toggle({
  label,
  checked,
  onChange,
  icon: Icon
}: {
  label: string;
  checked: boolean;
  onChange: (checked: boolean) => void;
  icon?: LucideIcon;
}) {
  return (
    <label className="toggleRow">
      <span>{Icon ? <Icon size={15} /> : null}{label}</span>
      <input type="checkbox" checked={checked} onChange={(event) => onChange(event.target.checked)} />
    </label>
  );
}
