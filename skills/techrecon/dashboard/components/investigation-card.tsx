import Link from 'next/link';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Server, FileText, StickyNote, Calendar } from 'lucide-react';
import { InvestigationStatusBadge } from './badges';

interface InvestigationSummary {
  systems: number;
  artifacts: number;
  notes: number;
  components: number;
  concepts: number;
  data_models: number;
}

interface Investigation {
  id: string;
  name: string;
  description?: string;
  status: string;
  goal: string;
  created_at?: string;
  summary?: InvestigationSummary;
}

type Stage = 'discovery' | 'analysis' | 'synthesis' | 'done';

const STAGE_STYLES: Record<Stage, string> = {
  discovery: 'bg-blue-500/15 text-blue-400 border-blue-500/30',
  analysis: 'bg-cyan-500/15 text-cyan-400 border-cyan-500/30',
  synthesis: 'bg-teal-500/15 text-teal-400 border-teal-500/30',
  done: 'bg-green-500/15 text-green-400 border-green-500/30',
};

function deriveStageBadge(status: string, summary?: InvestigationSummary): Stage {
  if (status === 'complete') return 'done';
  if (summary?.notes && summary.notes > 0) return 'synthesis';
  if ((summary?.components ?? 0) > 0 || (summary?.concepts ?? 0) > 0) return 'analysis';
  return 'discovery';
}

interface InvestigationCardProps {
  investigation: Investigation;
}

export function InvestigationCard({ investigation }: InvestigationCardProps) {
  const summary = investigation.summary;
  const stage = deriveStageBadge(investigation.status, summary);

  return (
    <Link href={`/techrecon/investigation/${investigation.id}`}>
      <Card className="hover:border-primary/50 transition-colors cursor-pointer h-full">
        <CardHeader className="pb-2">
          <div className="flex items-center justify-between gap-2">
            <CardTitle className="text-sm truncate">{investigation.name}</CardTitle>
            <div className="flex items-center gap-1.5 shrink-0">
              <Badge variant="outline" className={`text-xs ${STAGE_STYLES[stage]}`}>
                {stage}
              </Badge>
              <InvestigationStatusBadge status={investigation.status} />
            </div>
          </div>
        </CardHeader>
        <CardContent className="pt-0 space-y-3">
          {/* Goal */}
          {investigation.goal && (
            <p className="text-sm text-muted-foreground line-clamp-3">
              {investigation.goal}
            </p>
          )}

          {/* Summary counts */}
          {summary && (
            <div className="flex items-center gap-4 text-xs text-muted-foreground">
              <span className="flex items-center gap-1">
                <Server className="w-3 h-3" />
                {summary.systems}
              </span>
              <span className="flex items-center gap-1">
                <StickyNote className="w-3 h-3" />
                {summary.notes}
              </span>
              <span className="flex items-center gap-1">
                <FileText className="w-3 h-3" />
                {summary.artifacts}
              </span>
            </div>
          )}

          {/* Created date */}
          {investigation.created_at && (
            <div className="flex items-center gap-1 text-xs text-muted-foreground">
              <Calendar className="w-3 h-3" />
              {new Date(investigation.created_at).toLocaleDateString()}
            </div>
          )}
        </CardContent>
      </Card>
    </Link>
  );
}
