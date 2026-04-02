'use client';

import { type LucideIcon, Target, Search, FlaskConical, BarChart2, FileOutput, Check, X } from 'lucide-react';

export type SectionKey = 'scope' | 'discovery' | 'sensemaking' | 'analysis' | 'outputs';

export interface SectionNavItem {
  key: SectionKey;
  label: string;
  icon: LucideIcon;
  count?: number;
  hasReport?: boolean;
  hasAssessment?: boolean;
}

export interface SectionNavProps {
  items: SectionNavItem[];
  active: SectionKey;
  onSelect: (key: SectionKey) => void;
}

export const DEFAULT_SECTION_ICONS: Record<SectionKey, LucideIcon> = {
  scope: Target,
  discovery: Search,
  sensemaking: FlaskConical,
  analysis: BarChart2,
  outputs: FileOutput,
};

export function SectionNav({ items, active, onSelect }: SectionNavProps) {
  return (
    <nav className="flex flex-col gap-0.5">
      {items.map((item) => {
        const Icon = item.icon;
        const isActive = item.key === active;
        const isOutputs = item.key === 'outputs';

        return (
          <button
            key={item.key}
            onClick={() => onSelect(item.key)}
            className={[
              'flex flex-col items-start w-full px-3 py-2 rounded-sm text-left transition-colors',
              'border-l-4',
              isActive
                ? 'border-cyan-400 bg-cyan-500/10 text-cyan-300'
                : 'border-transparent hover:bg-accent/30 text-muted-foreground hover:text-foreground',
            ].join(' ')}
          >
            <span className="flex items-center gap-2 w-full">
              <Icon className="w-4 h-4 shrink-0" />
              <span className="text-sm font-medium flex-1">{item.label}</span>
              {item.count !== undefined && item.count > 0 && (
                <span className="text-xs font-semibold bg-muted text-muted-foreground rounded-full px-1.5 py-0.5 leading-none">
                  {item.count}
                </span>
              )}
            </span>

            {isOutputs && (item.hasReport !== undefined || item.hasAssessment !== undefined) && (
              <span className="flex gap-3 mt-1 ml-6 text-xs">
                {item.hasReport !== undefined && (
                  <span className={`flex items-center gap-0.5 ${item.hasReport ? 'text-green-400' : 'text-muted-foreground/50'}`}>
                    {item.hasReport ? <Check className="w-3 h-3" /> : <X className="w-3 h-3" />}
                    report
                  </span>
                )}
                {item.hasAssessment !== undefined && (
                  <span className={`flex items-center gap-0.5 ${item.hasAssessment ? 'text-green-400' : 'text-muted-foreground/50'}`}>
                    {item.hasAssessment ? <Check className="w-3 h-3" /> : <X className="w-3 h-3" />}
                    assessed
                  </span>
                )}
              </span>
            )}
          </button>
        );
      })}
    </nav>
  );
}
