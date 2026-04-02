'use client';

import { CheckCircle2 } from 'lucide-react';

export interface StageCompletion {
  scope: boolean;
  discovery: boolean;
  sensemaking: boolean;
  analysis: boolean;
  outputs: boolean;
}

const STAGES: { key: keyof StageCompletion; label: string }[] = [
  { key: 'scope', label: 'Scope' },
  { key: 'discovery', label: 'Discovery' },
  { key: 'sensemaking', label: 'Sensemaking' },
  { key: 'analysis', label: 'Analysis' },
  { key: 'outputs', label: 'Outputs' },
];

interface StageIndicatorProps {
  completion: StageCompletion;
}

export function StageIndicator({ completion }: StageIndicatorProps) {
  // The "current" stage is the first one that isn't complete
  const currentIndex = STAGES.findIndex(s => !completion[s.key]);
  const activeIndex = currentIndex === -1 ? STAGES.length : currentIndex;

  return (
    <div className="flex items-center gap-2 py-3 overflow-x-auto">
      {STAGES.map((stage, idx) => {
        const isCompleted = completion[stage.key];
        const isCurrent = idx === activeIndex;

        return (
          <div key={stage.key} className="flex items-center min-w-0">
            <div className="flex flex-col items-center gap-1">
              <div
                className={`w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold border-2 transition-colors ${
                  isCompleted
                    ? 'bg-green-500/20 border-green-500 text-green-400'
                    : isCurrent
                    ? 'bg-cyan-500/20 border-cyan-400 text-cyan-400'
                    : 'bg-muted/30 border-border/50 text-muted-foreground/40'
                }`}
              >
                {isCompleted ? (
                  <CheckCircle2 className="w-3.5 h-3.5" />
                ) : (
                  <span>{idx + 1}</span>
                )}
              </div>
              <span
                className={`text-xs whitespace-nowrap font-medium ${
                  isCompleted
                    ? 'text-green-400'
                    : isCurrent
                    ? 'text-cyan-400'
                    : 'text-muted-foreground/40'
                }`}
              >
                {stage.label}
              </span>
            </div>
            {idx < STAGES.length - 1 && (
              <div
                className={`h-0.5 w-10 sm:w-16 shrink-0 transition-colors ${
                  completion[stage.key] ? 'bg-green-500/50' : 'bg-border/40'
                }`}
              />
            )}
          </div>
        );
      })}
    </div>
  );
}
