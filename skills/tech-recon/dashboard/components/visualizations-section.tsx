'use client';

import Link from 'next/link';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import type { TechReconAnalysis, TechReconNote } from '@/lib/tech-recon';

const TYPE_COLORS: Record<string, string> = {
  comparison: 'bg-blue-500/20 text-blue-400 border-blue-500/40',
  trend: 'bg-purple-500/20 text-purple-400 border-purple-500/40',
  distribution: 'bg-amber-500/20 text-amber-400 border-amber-500/40',
  ranking: 'bg-cyan-500/20 text-cyan-400 border-cyan-500/40',
};

function typeColor(type: string): string {
  return TYPE_COLORS[type] ?? 'bg-slate-500/20 text-slate-400 border-slate-500/40';
}

interface AnalysisSectionProps {
  analyses: TechReconAnalysis[];
  vizPlanNotes: TechReconNote[];
  investigationId: string;
}

export function AnalysisSection({
  analyses,
  vizPlanNotes,
  investigationId,
}: AnalysisSectionProps) {
  const hasAnalyses = analyses.length > 0;
  const hasVizPlan = vizPlanNotes.length > 0;

  if (!hasAnalyses && !hasVizPlan) {
    return (
      <div className="rounded-lg border border-border/50 bg-muted/10 px-6 py-8 text-center space-y-3">
        <p className="text-sm text-muted-foreground">No visualization plan or analyses yet.</p>
        <p className="text-xs text-muted-foreground">
          Generate a visualization plan with:
        </p>
        <pre className="inline-block text-left text-xs bg-muted/30 rounded px-4 py-2 font-mono">
          {`uv run python .claude/skills/tech-recon/tech_recon.py plan-analyses --investigation ${investigationId}`}
        </pre>
        <p className="text-xs text-muted-foreground">
          Then ask Claude to review the plan and generate analysis code.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Analyses grid */}
      <div className="space-y-3">
        <h3 className="text-sm font-semibold text-foreground">
          Analyses ({analyses.length})
        </h3>

        {hasAnalyses ? (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {analyses.map((analysis) => (
              <Card key={analysis.id} className="bg-muted/10 border-border/50">
                <CardContent className="p-4 space-y-3">
                  <div className="flex items-start justify-between gap-2">
                    <Link
                      href={`/tech-recon/investigation/${investigationId}/analysis/${analysis.id}`}
                      className="text-cyan-400 font-semibold underline underline-offset-2 hover:text-blue-400 transition-colors text-sm leading-snug"
                    >
                      {analysis.title}
                    </Link>
                    <Badge
                      variant="outline"
                      className={`shrink-0 text-xs border ${typeColor(analysis.type)}`}
                    >
                      {analysis.type}
                    </Badge>
                  </div>

                  {analysis.description && (
                    <p className="text-xs text-muted-foreground line-clamp-2">
                      {analysis.description}
                    </p>
                  )}

                  <Button
                    variant="outline"
                    size="sm"
                    className="w-full text-xs"
                    asChild
                  >
                    <Link
                      href={`/tech-recon/investigation/${investigationId}/analysis/${analysis.id}`}
                    >
                      Run Analysis &rarr;
                    </Link>
                  </Button>
                </CardContent>
              </Card>
            ))}
          </div>
        ) : (
          <p className="text-sm text-muted-foreground italic">
            No analyses planned yet. Use{' '}
            <code className="text-xs bg-muted/30 rounded px-1 py-0.5 font-mono">
              tech-recon plan-analyses
            </code>{' '}
            to generate analysis plans.
          </p>
        )}
      </div>

      {/* Viz plan subsection */}
      {hasVizPlan && (
        <div className="space-y-3">
          <h4 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
            Visualization Plan
          </h4>
          <div className="space-y-3">
            {vizPlanNotes.map((note, idx) => (
              <div key={note.id}>
                {idx > 0 && <hr className="border-border/40 my-3" />}
                <pre className="text-xs bg-muted/20 border border-border/40 rounded p-4 font-mono overflow-x-auto whitespace-pre-wrap">
                  <code>{note.content ?? note.content_preview ?? '(no content)'}</code>
                </pre>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
