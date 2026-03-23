'use client';

import { DecisionTypeBadge } from './badges';

export interface Decision {
  id: string;
  name?: string;
  summary?: string;
  type?: string;
  alternatives?: string;
  created?: string;
}

function formatDate(iso?: string) {
  if (!iso) return '';
  return new Date(iso.replace('.000000000', '')).toLocaleDateString('en-US', {
    month: 'short', day: 'numeric', year: 'numeric',
  });
}

export function DecisionsList({ decisions }: { decisions: Decision[] }) {
  if (decisions.length === 0) {
    return (
      <div className="text-sm text-muted-foreground italic px-1">No decisions recorded.</div>
    );
  }

  return (
    <div className="space-y-3">
      {decisions.map((d) => (
        <div
          key={d.id}
          className="rounded-lg border border-border/40 bg-card/30 p-4 space-y-2"
        >
          <div className="flex flex-wrap items-center gap-2">
            <DecisionTypeBadge type={d.type} />
            {d.created && (
              <span className="ml-auto text-xs text-muted-foreground">{formatDate(d.created)}</span>
            )}
          </div>
          <p className="text-sm font-medium text-foreground/90">{d.summary ?? d.name}</p>
          {d.alternatives && (
            <p className="text-xs text-muted-foreground border-t border-border/30 pt-2 mt-1">
              <span className="font-medium text-muted-foreground/70">Alternatives: </span>
              {d.alternatives}
            </p>
          )}
        </div>
      ))}
    </div>
  );
}
