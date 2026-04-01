'use client';

import { useState } from 'react';
import { useParams } from 'next/navigation';
import Link from 'next/link';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { InvestigationStatusBadge } from '@/components/techrecon/badges';
import { SystemsGrid } from '@/components/techrecon/systems-grid';
import { InvestigationStage } from '@/components/techrecon/investigation-stage';
import { LiteratureList } from '@/components/techrecon/literature-list';
import { useInvestigationViewModel } from './useInvestigationViewModel';
import type { Note } from './useInvestigationViewModel';
import {
  ArrowLeft,
  RefreshCw,
  Target,
  ChevronRight,
  BookOpen,
  FileText,
  Puzzle,
  Lightbulb,
  Database,
  StickyNote,
} from 'lucide-react';

const linkClass =
  'text-cyan-400 font-semibold underline underline-offset-2 hover:text-blue-400 transition-colors';

function extractNoteTitle(note: Note): string {
  const match = note.content?.match(/^##\s+(.+)$/m);
  if (match) return match[1].trim();
  if (note.name) return note.name;
  return note.type ? note.type.replace(/-/g, ' ') : 'Note';
}

function CollapsibleNote({ note }: { note: Note }) {
  const [open, setOpen] = useState(false);
  const title = extractNoteTitle(note);

  return (
    <div className="border border-border/50 rounded-lg overflow-hidden">
      <button
        onClick={() => setOpen(!open)}
        className="w-full flex items-center gap-2 px-3 py-2.5 text-left hover:bg-accent/30 transition-colors"
      >
        <ChevronRight
          className={`w-4 h-4 shrink-0 text-muted-foreground transition-transform duration-200 ${
            open ? 'rotate-90' : ''
          }`}
        />
        {note.type && (
          <Badge variant="outline" className="text-xs shrink-0">
            {note.type.replace(/-/g, ' ')}
          </Badge>
        )}
        <span className="text-sm font-medium truncate">{title}</span>
      </button>
      {open && (
        <div className="px-4 py-3 border-t border-border/50 bg-card/50">
          <div className="prose prose-sm dark:prose-invert max-w-none">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>{note.content}</ReactMarkdown>
          </div>
        </div>
      )}
    </div>
  );
}

export default function InvestigationDetailPage() {
  const { id } = useParams<{ id: string }>();
  const vm = useInvestigationViewModel(id);

  if (vm.loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <RefreshCw className="w-6 h-6 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (vm.error || !vm.investigation) {
    return (
      <div className="min-h-screen">
        <header className="border-b border-border/50 bg-card/50 backdrop-blur-sm">
          <div className="container mx-auto px-4 py-4">
            <Link href="/techrecon" className={`flex items-center gap-2 text-sm ${linkClass}`}>
              <ArrowLeft className="w-4 h-4" />
              Back to TechRecon
            </Link>
          </div>
        </header>
        <main className="container mx-auto px-4 py-12 text-center">
          <p className="text-destructive">{vm.error || 'Investigation not found'}</p>
        </main>
      </div>
    );
  }

  const { investigation, systems, stage, stageCounts, keyFindings, literature, rawMaterials } = vm;

  return (
    <div className="min-h-screen">
      {/* Header */}
      <header className="border-b border-border/50 bg-card/50 backdrop-blur-sm">
        <div className="container mx-auto px-4 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-6">
              <Link href="/techrecon" className={`flex items-center gap-2 text-sm ${linkClass}`}>
                <ArrowLeft className="w-4 h-4" />
                TechRecon
              </Link>
              <div>
                <div className="flex items-center gap-3">
                  <h1 className="text-2xl font-bold bg-gradient-to-r from-cyan-400 to-blue-400 bg-clip-text text-transparent">
                    {investigation.name}
                  </h1>
                  <InvestigationStatusBadge status={investigation.status} />
                </div>
                {investigation.goal && (
                  <p className="text-xs text-muted-foreground mt-0.5 flex items-center gap-1.5">
                    <Target className="w-3 h-3" />
                    {investigation.goal}
                  </p>
                )}
              </div>
            </div>
            <Button
              variant="outline"
              size="sm"
              onClick={vm.refresh}
              className="border-border/50 hover:border-primary/50 hover:bg-primary/10"
            >
              <RefreshCw className="w-4 h-4 mr-2" />
              Refresh
            </Button>
          </div>
        </div>
      </header>

      {/* Stage Rail */}
      <div className="border-b border-border/50 bg-card/20">
        <div className="container mx-auto px-4">
          <InvestigationStage stage={stage} counts={stageCounts} />
        </div>
      </div>

      <main className="container mx-auto px-4 py-6">
        <div className="grid grid-cols-12 gap-6">
          {/* LEFT — Systems + Raw Materials */}
          <div className="col-span-12 lg:col-span-5 space-y-6">
            <section>
              <h2 className="text-xs font-semibold uppercase tracking-widest text-muted-foreground mb-3">
                Systems under investigation
              </h2>
              {systems.length > 0 ? (
                <SystemsGrid systems={systems} />
              ) : (
                <p className="text-sm text-muted-foreground italic">
                  No systems added yet.
                </p>
              )}
            </section>

            {(rawMaterials.artifacts > 0 ||
              rawMaterials.components > 0 ||
              rawMaterials.concepts > 0 ||
              rawMaterials.dataModels > 0) && (
              <section>
                <h2 className="text-xs font-semibold uppercase tracking-widest text-muted-foreground mb-3">
                  Raw materials
                </h2>
                <div className="flex flex-wrap gap-2">
                  {rawMaterials.artifacts > 0 && (
                    <div className="flex items-center gap-1.5 text-sm px-3 py-1.5 bg-muted/40 rounded-lg border border-border/40">
                      <FileText className="w-3.5 h-3.5 text-muted-foreground" />
                      <span className="font-medium">{rawMaterials.artifacts}</span>
                      <span className="text-muted-foreground">artifacts</span>
                    </div>
                  )}
                  {rawMaterials.components > 0 && (
                    <div className="flex items-center gap-1.5 text-sm px-3 py-1.5 bg-muted/40 rounded-lg border border-border/40">
                      <Puzzle className="w-3.5 h-3.5 text-muted-foreground" />
                      <span className="font-medium">{rawMaterials.components}</span>
                      <span className="text-muted-foreground">components</span>
                    </div>
                  )}
                  {rawMaterials.concepts > 0 && (
                    <div className="flex items-center gap-1.5 text-sm px-3 py-1.5 bg-muted/40 rounded-lg border border-border/40">
                      <Lightbulb className="w-3.5 h-3.5 text-muted-foreground" />
                      <span className="font-medium">{rawMaterials.concepts}</span>
                      <span className="text-muted-foreground">concepts</span>
                    </div>
                  )}
                  {rawMaterials.dataModels > 0 && (
                    <div className="flex items-center gap-1.5 text-sm px-3 py-1.5 bg-muted/40 rounded-lg border border-border/40">
                      <Database className="w-3.5 h-3.5 text-muted-foreground" />
                      <span className="font-medium">{rawMaterials.dataModels}</span>
                      <span className="text-muted-foreground">data models</span>
                    </div>
                  )}
                </div>
              </section>
            )}
          </div>

          {/* RIGHT — Key Findings + Literature */}
          <div className="col-span-12 lg:col-span-7 space-y-6">
            <section>
              <h2 className="text-xs font-semibold uppercase tracking-widest text-muted-foreground mb-3">
                Key findings
              </h2>
              {keyFindings.length > 0 ? (
                <div className="space-y-1.5">
                  {keyFindings.map((note) => (
                    <CollapsibleNote key={note.id} note={note} />
                  ))}
                </div>
              ) : (
                <Card className="border-dashed border-border/50">
                  <CardContent className="py-8 flex flex-col items-center gap-2 text-center">
                    <StickyNote className="w-8 h-8 text-muted-foreground/40" />
                    <p className="text-sm text-muted-foreground">No synthesis notes yet</p>
                    <p className="text-xs text-muted-foreground/70">
                      Add architecture or assessment notes using{' '}
                      <code className="bg-muted px-1 py-0.5 rounded">techrecon add-note</code>
                    </p>
                  </CardContent>
                </Card>
              )}
            </section>

            <section>
              <h2 className="text-xs font-semibold uppercase tracking-widest text-muted-foreground mb-3 flex items-center gap-2">
                <BookOpen className="w-3.5 h-3.5" />
                Literature
                {literature.length > 0 && (
                  <Badge variant="secondary" className="text-xs ml-1">
                    {literature.length}
                  </Badge>
                )}
              </h2>
              <LiteratureList papers={literature} />
            </section>
          </div>
        </div>
      </main>

      <footer className="border-t border-border/50 mt-8">
        <div className="container mx-auto px-4 py-4">
          <p className="text-xs text-muted-foreground text-center">
            TechRecon &bull; Powered by TypeDB + Next.js
          </p>
        </div>
      </footer>
    </div>
  );
}
