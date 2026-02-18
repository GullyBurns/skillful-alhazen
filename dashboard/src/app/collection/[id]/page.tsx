'use client';

import { useState, useEffect, use } from 'react';
import Link from 'next/link';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Separator } from '@/components/ui/separator';
import {
  ArrowLeft,
  RefreshCw,
  FileText,
  ChevronDown,
  ChevronRight,
  Library,
} from 'lucide-react';

// Helper to extract value from TypeDB fetch result
function getValue(attr: Array<{ value: unknown }> | undefined): string | null {
  if (!attr || attr.length === 0) return null;
  const val = String(attr[0].value);
  // Unescape newlines/tabs — handle double-escaped (\\n) before single-escaped (\n)
  return val.replace(/\\\\n/g, '\n').replace(/\\n/g, '\n')
            .replace(/\\\\t/g, '\t').replace(/\\t/g, '\t');
}

function getNumber(attr: Array<{ value: unknown }> | undefined): number | null {
  if (!attr || attr.length === 0) return null;
  return Number(attr[0].value);
}

interface PaperNotesProps {
  paperId: string;
}

function PaperNotes({ paperId }: PaperNotesProps) {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const [notes, setNotes] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function fetchNotes() {
      try {
        const res = await fetch(`/api/jobhunt/notes/${paperId}`);
        if (!res.ok) throw new Error('Failed to fetch notes');
        const data = await res.json();
        setNotes(data.notes || []);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Unknown error');
      } finally {
        setLoading(false);
      }
    }
    fetchNotes();
  }, [paperId]);

  if (loading) {
    return (
      <div className="flex items-center gap-2 py-2 text-sm text-muted-foreground">
        <RefreshCw className="w-3 h-3 animate-spin" />
        Loading notes...
      </div>
    );
  }

  if (error) {
    return (
      <p className="text-sm text-destructive py-2">Failed to load notes: {error}</p>
    );
  }

  if (notes.length === 0) {
    return (
      <p className="text-sm text-muted-foreground py-2">No notes for this paper.</p>
    );
  }

  return (
    <div className="space-y-4 pt-2">
      {notes.map((note, idx) => {
        const n = note.n || note;
        const name = getValue(n.name);
        const content = getValue(n.content);
        const confidence = getNumber(n.confidence);

        return (
          <div key={idx} className="text-sm">
            <div className="flex items-center gap-2 mb-1">
              {name && <span className="font-medium">{name}</span>}
              {confidence != null && (
                <Badge variant="outline" className="text-xs">
                  confidence: {confidence}
                </Badge>
              )}
            </div>
            {content && (
              <div className="prose prose-sm max-w-none dark:prose-invert">
                <ReactMarkdown remarkPlugins={[remarkGfm]}>
                  {content}
                </ReactMarkdown>
              </div>
            )}
            {idx < notes.length - 1 && <Separator className="mt-4" />}
          </div>
        );
      })}
    </div>
  );
}

interface CollectionPageProps {
  params: Promise<{ id: string }>;
}

export default function CollectionPage({ params }: CollectionPageProps) {
  const { id } = use(params);
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [expandedPapers, setExpandedPapers] = useState<Set<string>>(new Set());

  useEffect(() => {
    async function fetchCollection() {
      setLoading(true);
      setError(null);
      try {
        const res = await fetch(`/api/jobhunt/collection/${id}`);
        if (!res.ok) throw new Error('Failed to fetch collection');
        const json = await res.json();
        setData(json);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Unknown error');
      } finally {
        setLoading(false);
      }
    }
    fetchCollection();
  }, [id]);

  const togglePaper = (paperId: string) => {
    setExpandedPapers((prev) => {
      const next = new Set(prev);
      if (next.has(paperId)) {
        next.delete(paperId);
      } else {
        next.add(paperId);
      }
      return next;
    });
  };

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <RefreshCw className="w-8 h-8 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="min-h-screen p-8">
        <Link href="/">
          <Button variant="ghost" className="mb-4">
            <ArrowLeft className="w-4 h-4 mr-2" />
            Back to Dashboard
          </Button>
        </Link>
        <div className="bg-destructive/10 text-destructive px-4 py-3 rounded-lg">
          <strong>Error:</strong> {error || 'Collection not found'}
        </div>
      </div>
    );
  }

  const collection = data.collection?.c || data.collection;
  const members = data.members || [];

  const name = getValue(collection?.name) || 'Unknown Collection';
  const description = getValue(collection?.description);

  return (
    <div className="min-h-screen">
      {/* Header */}
      <header className="border-b border-border/50 bg-card/50 backdrop-blur-sm">
        <div className="container mx-auto px-4 py-4">
          <Link href="/">
            <Button variant="ghost" size="sm" className="mb-2 hover:bg-primary/10">
              <ArrowLeft className="w-4 h-4 mr-2" />
              Back to Dashboard
            </Button>
          </Link>
          <div className="flex items-start justify-between">
            <div>
              <h1 className="text-2xl font-bold bg-gradient-to-r from-indigo-400 to-purple-400 bg-clip-text text-transparent flex items-center gap-3">
                <Library className="w-6 h-6 text-indigo-400" />
                {name}
              </h1>
              {description && (
                <p className="text-muted-foreground mt-1">{description}</p>
              )}
            </div>
            <Badge variant="secondary">{members.length} papers</Badge>
          </div>
        </div>
      </header>

      <main className="container mx-auto px-4 py-6 space-y-4">
        {members.map((member: { m: Record<string, unknown> }, idx: number) => {
          const m = member.m || member;
          // eslint-disable-next-line @typescript-eslint/no-explicit-any
          const paperId = getValue((m as any).id);
          // eslint-disable-next-line @typescript-eslint/no-explicit-any
          const paperName = getValue((m as any).name) || 'Untitled Paper';
          const isExpanded = paperId ? expandedPapers.has(paperId) : false;

          return (
            <Card key={paperId || idx}>
              <CardHeader className="pb-3">
                <CardTitle
                  className="text-sm flex items-center gap-2 cursor-pointer hover:text-primary transition-colors"
                  onClick={() => paperId && togglePaper(paperId)}
                >
                  {isExpanded ? (
                    <ChevronDown className="w-4 h-4 shrink-0" />
                  ) : (
                    <ChevronRight className="w-4 h-4 shrink-0" />
                  )}
                  <FileText className="w-4 h-4 shrink-0 text-muted-foreground" />
                  <span className="flex-1">{paperName}</span>
                </CardTitle>
              </CardHeader>
              {isExpanded && paperId && (
                <CardContent>
                  <PaperNotes paperId={paperId} />
                </CardContent>
              )}
            </Card>
          );
        })}

        {members.length === 0 && (
          <Card>
            <CardContent className="py-8">
              <div className="text-center text-muted-foreground">
                <FileText className="w-12 h-12 mx-auto mb-4 opacity-50" />
                <p>No papers in this collection.</p>
              </div>
            </CardContent>
          </Card>
        )}
      </main>
    </div>
  );
}
