'use client';

import { FeasibilityBadge } from './badges';
import { Target, Boxes, Database, Zap, BarChart2 } from 'lucide-react';

const PHASES = [
  { key: 'goals',               number: 1, label: 'Goal',        icon: Target,    color: 'border-violet-500/40 bg-violet-500/5' },
  { key: 'dm-entity-schema',    number: 2, label: 'Schema',      icon: Boxes,     color: 'border-blue-500/40 bg-blue-500/5' },
  { key: 'dm-source-schema',    number: 3, label: 'Sources',     icon: Database,  color: 'border-cyan-500/40 bg-cyan-500/5' },
  { key: 'dm-derivation-skill', number: 4, label: 'Derivation',  icon: Zap,       color: 'border-emerald-500/40 bg-emerald-500/5' },
  { key: 'dm-analysis-skill',   number: 5, label: 'Analysis',    icon: BarChart2, color: 'border-amber-500/40 bg-amber-500/5' },
];

interface PhaseItem {
  id: string;
  name: string;
  feasibility?: string;
  phase?: number;
}

interface Goal {
  id: string;
  name: string;
  description?: string;
}

interface PhaseItemsMap {
  [key: string]: PhaseItem[];
}

interface PhaseOverviewProps {
  phaseItems: PhaseItemsMap;
  goals?: Goal[];
  openGapCountsByPhase?: Record<string, number>;
}

export function PhaseOverview({ phaseItems, goals, openGapCountsByPhase }: PhaseOverviewProps) {
  return (
    <div className="grid grid-cols-1 sm:grid-cols-5 gap-3">
      {PHASES.map(({ key, number, label, icon: Icon, color }) => {
        const items = key === 'goals' ? (goals ?? []) : (phaseItems[key] ?? []);
        const gapCount = openGapCountsByPhase?.[String(number)] ?? 0;
        const isEmpty = items.length === 0;

        return (
          <div
            key={key}
            className={`rounded-lg border p-3 ${isEmpty ? 'border-border/30 bg-muted/5 opacity-60' : color}`}
          >
            <div className="flex items-center gap-2 mb-2">
              <Icon className="w-4 h-4 text-muted-foreground flex-shrink-0" />
              <span className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">
                {number}. {label}
              </span>
            </div>

            {isEmpty ? (
              <p className="text-xs text-muted-foreground italic">Not defined</p>
            ) : (
              <div className="space-y-2">
                {items.map((item: PhaseItem | Goal) => (
                  <div key={item.id}>
                    <p className="text-xs text-foreground/90 leading-snug line-clamp-2">
                      {item.name}
                    </p>
                    {'feasibility' in item && item.feasibility && (
                      <div className="mt-1">
                        <FeasibilityBadge feasibility={item.feasibility} />
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}

            {gapCount > 0 && (
              <div className="mt-2 text-xs text-orange-400">
                {gapCount} open gap{gapCount !== 1 ? 's' : ''}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
