'use client';

import Link from 'next/link';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Target, Layers } from 'lucide-react';
import type { Investigation } from '@/lib/tech-recon';

const linkClass =
  'text-cyan-400 font-semibold underline underline-offset-2 hover:text-blue-400 transition-colors';

const STATUS_COLORS: Record<string, string> = {
  active: 'bg-green-500/20 text-green-400 border-green-500/30',
  completed: 'bg-blue-500/20 text-blue-400 border-blue-500/30',
  paused: 'bg-yellow-500/20 text-yellow-400 border-yellow-500/30',
  archived: 'bg-slate-500/20 text-slate-300 border-slate-500/30',
};

function getStatusColor(status: string | null | undefined): string {
  if (!status) return 'bg-slate-500/20 text-slate-300 border-slate-500/30';
  return STATUS_COLORS[status.toLowerCase()] || 'bg-slate-500/20 text-slate-300 border-slate-500/30';
}

interface InvestigationWithSystems extends Investigation {
  systems_count?: number;
}

export function InvestigationCard({ investigation }: { investigation: InvestigationWithSystems }) {
  return (
    <Card className="border-border/50 bg-card/50 hover:border-primary/30 hover:bg-card/80 transition-all">
      <CardHeader className="pb-2">
        <div className="flex items-start justify-between gap-2">
          <CardTitle className="text-base">
            <Link
              href={`/tech-recon/investigation/${investigation.id}`}
              className={linkClass}
            >
              {investigation.name}
            </Link>
          </CardTitle>
          <Badge className={`${getStatusColor(investigation.status)} shrink-0 text-xs`}>
            {investigation.status || 'unknown'}
          </Badge>
        </div>
      </CardHeader>
      <CardContent className="space-y-3">
        {investigation.goal && (
          <p className="text-sm text-muted-foreground flex items-start gap-1.5">
            <Target className="w-3.5 h-3.5 shrink-0 mt-0.5 text-muted-foreground/60" />
            <span className="line-clamp-2">{investigation.goal}</span>
          </p>
        )}
        {investigation.systems_count !== undefined && (
          <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
            <Layers className="w-3.5 h-3.5" />
            <span>{investigation.systems_count} system{investigation.systems_count !== 1 ? 's' : ''}</span>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
