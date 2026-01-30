import { LucideIcon } from 'lucide-react';

interface SectionHeaderProps {
  title: string;
  icon: LucideIcon;
  description?: string;
}

export function SectionHeader({ title, icon: Icon, description }: SectionHeaderProps) {
  return (
    <div className="flex items-center gap-4 mb-6">
      <div className="flex items-center justify-center w-11 h-11 rounded-venn-lg bg-gradient-to-br from-venn-amber to-venn-copper shadow-md shadow-venn-amber/10">
        <Icon className="w-5 h-5 text-venn-navy" />
      </div>
      <div>
        <h2 className="text-lg font-bold text-venn-navy">{title}</h2>
        {description && <p className="text-sm text-slate-500 mt-0.5">{description}</p>}
      </div>
    </div>
  );
}
