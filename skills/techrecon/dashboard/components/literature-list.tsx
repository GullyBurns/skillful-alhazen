'use client';

import { useState } from 'react';
import { ChevronDown, ChevronUp, BookOpen, ExternalLink } from 'lucide-react';
import type { Paper } from '@/components/techrecon/types';

const COLLAPSED_COUNT = 3;

interface LiteratureListProps {
  papers: Paper[];
  emptyMessage?: string;
}

export function LiteratureList({
  papers,
  emptyMessage = 'No literature linked yet.',
}: LiteratureListProps) {
  const [expanded, setExpanded] = useState(false);

  if (papers.length === 0) {
    return (
      <p className="text-sm text-muted-foreground italic">{emptyMessage}</p>
    );
  }

  const visible = expanded ? papers : papers.slice(0, COLLAPSED_COUNT);
  const hasMore = papers.length > COLLAPSED_COUNT;

  return (
    <div className="space-y-2">
      {visible.map((paper) => (
        <div
          key={paper.id}
          className="flex items-start gap-2 text-sm p-2 rounded-lg bg-muted/30 hover:bg-muted/50 transition-colors"
        >
          <BookOpen className="w-3.5 h-3.5 text-muted-foreground shrink-0 mt-0.5" />
          <div className="flex-1 min-w-0">
            <p className="text-foreground/90 leading-snug line-clamp-2">{paper.citation}</p>
          </div>
          {paper.doi && (
            <a
              href={`https://doi.org/${paper.doi}`}
              target="_blank"
              rel="noopener noreferrer"
              className="shrink-0 text-primary hover:text-primary/70 transition-colors"
              title={`DOI: ${paper.doi}`}
            >
              <ExternalLink className="w-3.5 h-3.5" />
            </a>
          )}
        </div>
      ))}

      {hasMore && (
        <button
          onClick={() => setExpanded(!expanded)}
          className="flex items-center gap-1 text-xs text-muted-foreground hover:text-primary transition-colors mt-1"
        >
          {expanded ? (
            <>
              <ChevronUp className="w-3.5 h-3.5" />
              Show fewer
            </>
          ) : (
            <>
              <ChevronDown className="w-3.5 h-3.5" />
              {papers.length - COLLAPSED_COUNT} more papers
            </>
          )}
        </button>
      )}
    </div>
  );
}
