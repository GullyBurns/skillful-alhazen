'use client';

import { CheckCircle2 } from 'lucide-react';

const STAGES = [
  { key: 'scoping', label: 'Scoping' },
  { key: 'ingesting', label: 'Ingesting' },
  { key: 'sensemaking', label: 'Sensemaking' },
  { key: 'viz-planning', label: 'Viz Planning' },
  { key: 'analysis', label: 'Analysis' },
  { key: 'synthesis', label: 'Synthesis' },
  { key: 'evaluating', label: 'Evaluating' },
  { key: 'done', label: 'Done' },
];

interface StageIndicatorProps {
  status: string;
}

export function StageIndicator({ status }: StageIndicatorProps) {
  const currentIndex = STAGES.findIndex((s) => s.key === status?.toLowerCase());
  const activeIndex = currentIndex >= 0 ? currentIndex : 0;

  return (
    <div className="flex items-center gap-0 py-3 overflow-x-auto">
      {STAGES.map((stage, idx) => {
        const isCompleted = idx < activeIndex;
        const isCurrent = idx === activeIndex;
        const isFuture = idx > activeIndex;

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
                className={`h-0.5 w-6 sm:w-10 mx-1 shrink-0 transition-colors ${
                  idx < activeIndex ? 'bg-green-500/50' : 'bg-border/40'
                }`}
              />
            )}
          </div>
        );
      })}
    </div>
  );
}
