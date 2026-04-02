'use client';

import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { Target, ListChecks } from 'lucide-react';
import { Card, CardContent } from '@/components/ui/card';
import type { Investigation } from '@/lib/tech-recon';

interface ScopeSectionProps {
  investigation: Investigation;
}

export function ScopeSection({ investigation }: ScopeSectionProps) {
  return (
    <div className="space-y-4">
      <Card className="bg-card/40 border-border/50">
        <CardContent className="pt-5 space-y-2">
          <div className="flex items-center gap-2">
            <Target className="w-4 h-4 text-cyan-400 shrink-0" />
            <span className="text-xs font-semibold uppercase tracking-wide text-cyan-400">Goal</span>
          </div>
          {investigation.goal ? (
            <div className="prose prose-sm dark:prose-invert max-w-none">
              <ReactMarkdown remarkPlugins={[remarkGfm]}>{investigation.goal}</ReactMarkdown>
            </div>
          ) : (
            <p className="text-sm italic text-muted-foreground">No goal defined.</p>
          )}
        </CardContent>
      </Card>

      <Card className="bg-card/40 border-border/50">
        <CardContent className="pt-5 space-y-2">
          <div className="flex items-center gap-2">
            <ListChecks className="w-4 h-4 text-green-400 shrink-0" />
            <span className="text-xs font-semibold uppercase tracking-wide text-green-400">Success Criteria</span>
          </div>
          {investigation.criteria ? (
            <div className="prose prose-sm dark:prose-invert max-w-none">
              <ReactMarkdown remarkPlugins={[remarkGfm]}>{investigation.criteria}</ReactMarkdown>
            </div>
          ) : (
            <p className="text-sm italic text-muted-foreground">No criteria defined.</p>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
