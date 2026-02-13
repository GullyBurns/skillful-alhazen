'use client';

import { useState } from 'react';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip';
import { ExternalLink, MessageSquare, ThumbsUp, ThumbsDown, Loader2 } from 'lucide-react';

export interface Candidate {
  id: string;
  title: string;
  url: string;
  location: string;
  relevance: number | null;
  status: string;
  external_id: string;
  discovered_at: string;
  triage_reason: string | null;
}

interface CandidatesTableProps {
  candidates: Candidate[];
  onPromote?: (id: string) => Promise<void>;
  onDismiss?: (id: string) => Promise<void>;
}

function extractRole(title: string): string {
  if (title.includes(' @ ')) {
    return title.split(' @ ')[0].trim();
  }
  return title;
}

function extractCompany(title: string): string {
  if (title.includes(' @ ')) {
    return title.split(' @ ').slice(1).join(' @ ').trim();
  }
  return '';
}

function extractSource(url: string): string {
  try {
    const hostname = new URL(url).hostname;
    if (hostname.includes('greenhouse')) return 'Greenhouse';
    if (hostname.includes('lever')) return 'Lever';
    if (hostname.includes('linkedin')) return 'LinkedIn';
    if (hostname.includes('remotive')) return 'Remotive';
    if (hostname.includes('adzuna')) return 'Adzuna';
    return hostname.replace('www.', '').split('.')[0];
  } catch {
    return 'Unknown';
  }
}

function formatDate(dateStr: string): string {
  if (!dateStr) return '';
  try {
    const d = new Date(dateStr);
    return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
  } catch {
    return dateStr;
  }
}

const RELEVANCE_COLORS: Record<string, string> = {
  high: 'bg-green-100 text-green-800',
  medium: 'bg-yellow-100 text-yellow-800',
  low: 'bg-gray-100 text-gray-800',
};

function relevanceBucket(score: number | null): string {
  if (score === null || score === undefined) return 'low';
  if (score >= 0.7) return 'high';
  if (score >= 0.4) return 'medium';
  return 'low';
}

const STATUS_COLORS: Record<string, string> = {
  reviewed: 'bg-blue-100 text-blue-800',
  dismissed: 'bg-gray-100 text-gray-500',
  promoted: 'bg-green-100 text-green-800',
  new: 'bg-yellow-100 text-yellow-800',
};

export function CandidatesTable({ candidates, onPromote, onDismiss }: CandidatesTableProps) {
  const [loadingActions, setLoadingActions] = useState<Record<string, boolean>>({});
  const showActions = !!(onPromote || onDismiss);

  const handleAction = async (id: string, action: 'promote' | 'dismiss') => {
    setLoadingActions((prev) => ({ ...prev, [id]: true }));
    try {
      if (action === 'promote' && onPromote) {
        await onPromote(id);
      } else if (action === 'dismiss' && onDismiss) {
        await onDismiss(id);
      }
    } finally {
      setLoadingActions((prev) => ({ ...prev, [id]: false }));
    }
  };

  return (
    <div className="space-y-4">
      {/* Summary */}
      <div className="flex items-center gap-4 p-4 bg-muted rounded-lg">
        <div className="flex-1">
          <div className="text-sm font-medium">
            {showActions ? 'Reviewed Candidates' : 'All Triaged Candidates'}
          </div>
          <div className="text-xs text-muted-foreground">
            {showActions
              ? 'Job postings discovered by the forager and marked as relevant by triage'
              : 'All candidates that have been triaged (reviewed, dismissed, promoted)'}
          </div>
        </div>
        <div className="text-right">
          <div className="text-2xl font-bold">{candidates.length}</div>
          <div className="text-xs text-muted-foreground">candidates</div>
        </div>
      </div>

      {/* Table */}
      <TooltipProvider>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Role</TableHead>
              <TableHead>Company</TableHead>
              <TableHead>Location</TableHead>
              <TableHead>Source</TableHead>
              <TableHead>Score</TableHead>
              {!showActions && <TableHead>Status</TableHead>}
              <TableHead>Reason</TableHead>
              <TableHead>Discovered</TableHead>
              {showActions && <TableHead className="text-right">Actions</TableHead>}
            </TableRow>
          </TableHeader>
          <TableBody>
            {candidates.map((c) => {
              const isLoading = loadingActions[c.id];
              return (
                <TableRow key={c.id} className={isLoading ? 'opacity-50' : ''}>
                  <TableCell className="font-medium max-w-sm">
                    <a
                      href={c.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="flex items-center gap-1 text-primary hover:underline"
                    >
                      <span className="truncate">{extractRole(c.title)}</span>
                      <ExternalLink className="w-3 h-3 flex-shrink-0" />
                    </a>
                  </TableCell>
                  <TableCell className="text-sm">
                    {extractCompany(c.title) || <span className="text-muted-foreground">-</span>}
                  </TableCell>
                  <TableCell className="text-sm text-muted-foreground">
                    {c.location || 'Not specified'}
                  </TableCell>
                  <TableCell>
                    <Badge variant="outline" className="text-xs">
                      {extractSource(c.url)}
                    </Badge>
                  </TableCell>
                  <TableCell>
                    {c.relevance !== null && c.relevance !== undefined ? (
                      <Badge className={RELEVANCE_COLORS[relevanceBucket(c.relevance)]}>
                        {(c.relevance * 100).toFixed(0)}%
                      </Badge>
                    ) : (
                      <span className="text-muted-foreground text-sm">-</span>
                    )}
                  </TableCell>
                  {!showActions && (
                    <TableCell>
                      <Badge className={STATUS_COLORS[c.status] || 'bg-gray-100 text-gray-600'}>
                        {c.status}
                      </Badge>
                    </TableCell>
                  )}
                  <TableCell>
                    {c.triage_reason ? (
                      <Tooltip>
                        <TooltipTrigger asChild>
                          <button className="text-muted-foreground hover:text-foreground transition-colors">
                            <MessageSquare className="w-4 h-4" />
                          </button>
                        </TooltipTrigger>
                        <TooltipContent>
                          <p>{c.triage_reason}</p>
                        </TooltipContent>
                      </Tooltip>
                    ) : (
                      <span className="text-muted-foreground text-sm">-</span>
                    )}
                  </TableCell>
                  <TableCell className="text-sm text-muted-foreground">
                    {formatDate(c.discovered_at)}
                  </TableCell>
                  {showActions && (
                    <TableCell className="text-right">
                      <div className="flex items-center justify-end gap-1">
                        {isLoading ? (
                          <Loader2 className="w-4 h-4 animate-spin text-muted-foreground" />
                        ) : (
                          <>
                            {onPromote && (
                              <Button
                                variant="ghost"
                                size="icon"
                                className="h-7 w-7 hover:bg-green-100 hover:text-green-700"
                                onClick={() => handleAction(c.id, 'promote')}
                              >
                                <ThumbsUp className="w-4 h-4" />
                              </Button>
                            )}
                            {onDismiss && (
                              <Button
                                variant="ghost"
                                size="icon"
                                className="h-7 w-7 hover:bg-red-100 hover:text-red-700"
                                onClick={() => handleAction(c.id, 'dismiss')}
                              >
                                <ThumbsDown className="w-4 h-4" />
                              </Button>
                            )}
                          </>
                        )}
                      </div>
                    </TableCell>
                  )}
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
      </TooltipProvider>

      {candidates.length === 0 && (
        <div className="text-center py-8 text-muted-foreground">
          {showActions
            ? 'No reviewed candidates found. Run the forager and triage to discover job postings.'
            : 'No triaged candidates found.'}
        </div>
      )}
    </div>
  );
}
