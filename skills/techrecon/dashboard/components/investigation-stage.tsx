'use client';

import type { Stage, StageCounts } from '@/components/techrecon/types';

interface StageNode {
  key: Stage;
  label: string;
  sublabel: (counts: StageCounts) => string;
}

const STAGES: StageNode[] = [
  {
    key: 'discovery',
    label: 'Discovery',
    sublabel: (c) => {
      const parts = [];
      if (c.discovery.systems > 0) parts.push(`${c.discovery.systems} sys`);
      if (c.discovery.artifacts > 0) parts.push(`${c.discovery.artifacts} art`);
      return parts.join(' · ') || '—';
    },
  },
  {
    key: 'analysis',
    label: 'Analysis',
    sublabel: (c) => {
      const parts = [];
      if (c.analysis.components > 0) parts.push(`${c.analysis.components} comp`);
      if (c.analysis.concepts > 0) parts.push(`${c.analysis.concepts} conc`);
      return parts.join(' · ') || '—';
    },
  },
  {
    key: 'synthesis',
    label: 'Synthesis',
    sublabel: (c) => {
      const total = c.synthesis.archNotes + c.synthesis.assessNotes;
      return total > 0 ? `${total} notes` : '—';
    },
  },
  {
    key: 'done',
    label: 'Done',
    sublabel: (c) => (c.done.complete ? 'complete' : '—'),
  },
];

const STAGE_ORDER: Stage[] = ['discovery', 'analysis', 'synthesis', 'done'];

function stageIndex(stage: Stage): number {
  return STAGE_ORDER.indexOf(stage);
}

interface InvestigationStageProps {
  stage: Stage;
  counts: StageCounts;
}

export function InvestigationStage({ stage, counts }: InvestigationStageProps) {
  const activeIdx = stageIndex(stage);

  return (
    <div className="w-full px-2 py-4">
      <div className="flex items-start justify-between relative">
        {/* Connector line — full width, behind nodes */}
        <div
          className="absolute top-[10px] left-0 right-0 h-px bg-border/50"
          style={{ zIndex: 0 }}
        />

        {STAGES.map((s, idx) => {
          const reached = idx <= activeIdx;
          const isActive = idx === activeIdx;

          return (
            <div
              key={s.key}
              className="flex flex-col items-center gap-1.5 relative"
              style={{ zIndex: 1, flex: '1 1 0' }}
            >
              {/* Node circle */}
              <div
                className={[
                  'w-5 h-5 rounded-full border-2 flex items-center justify-center transition-all duration-300',
                  reached
                    ? 'bg-primary border-primary'
                    : 'bg-background border-border/50',
                  isActive
                    ? 'ring-2 ring-primary/40 ring-offset-2 ring-offset-background scale-110'
                    : '',
                ]
                  .filter(Boolean)
                  .join(' ')}
              >
                {reached && (
                  <div className="w-2 h-2 rounded-full bg-background" />
                )}
              </div>

              {/* Label */}
              <span
                className={`text-xs font-semibold tracking-wide ${
                  isActive
                    ? 'text-primary'
                    : reached
                    ? 'text-foreground/80'
                    : 'text-muted-foreground'
                }`}
              >
                {s.label}
              </span>

              {/* Sub-label counts */}
              <span className="text-[10px] text-muted-foreground text-center leading-tight px-1">
                {s.sublabel(counts)}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
