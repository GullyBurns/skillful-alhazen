'use client';

import { useState, use } from 'react';
import Link from 'next/link';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import {
  ArrowLeft,
  ExternalLink,
  RefreshCw,
  Star,
  GitBranch,
  Scale,
  Package,
  Puzzle,
  FileText,
  Database,
  BarChart2,
  Workflow,
  ChevronDown,
  ChevronRight,
  Brain,
  BookOpen,
} from 'lucide-react';
import { MaturityBadge, LanguageBadge, TypeBadge, FormatBadge, GranularityBadge } from '@/components/techrecon/badges';
import { TagChips } from '@/components/techrecon/tag-chips';
import { LiteratureList } from '@/components/techrecon/literature-list';
import { useSystemViewModel } from './useSystemViewModel';
import type { Note } from './useSystemViewModel';

interface SystemPageProps {
  params: Promise<{ id: string }>;
}

const linkClass =
  'text-cyan-400 font-semibold underline underline-offset-2 hover:text-blue-400 transition-colors';

function CollapsibleSection({
  title,
  count,
  icon: Icon,
  children,
  defaultOpen = false,
}: {
  title: string;
  count: number;
  icon: React.ComponentType<{ className?: string }>;
  children: React.ReactNode;
  defaultOpen?: boolean;
}) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <div className="border border-border/50 rounded-lg overflow-hidden">
      <button
        onClick={() => setOpen(!open)}
        className="w-full flex items-center gap-2 px-4 py-3 text-left bg-muted/20 hover:bg-muted/40 transition-colors"
      >
        {open ? (
          <ChevronDown className="w-4 h-4 shrink-0 text-muted-foreground" />
        ) : (
          <ChevronRight className="w-4 h-4 shrink-0 text-muted-foreground" />
        )}
        <Icon className="w-4 h-4 text-muted-foreground" />
        <span className="text-sm font-medium">{title}</span>
        <Badge variant="secondary" className="ml-auto text-xs">
          {count}
        </Badge>
      </button>
      {open && <div className="p-4 border-t border-border/50">{children}</div>}
    </div>
  );
}

function NoteCard({ note }: { note: Note }) {
  const [open, setOpen] = useState(false);
  const title = note.content?.match(/^##\s+(.+)$/m)?.[1]?.trim() ?? note.name ?? 'Note';
  return (
    <div className="border border-border/40 rounded-lg overflow-hidden">
      <button
        onClick={() => setOpen(!open)}
        className="w-full flex items-center gap-2 px-3 py-2 text-left hover:bg-accent/20 transition-colors"
      >
        <ChevronRight
          className={`w-3.5 h-3.5 shrink-0 text-muted-foreground transition-transform ${open ? 'rotate-90' : ''}`}
        />
        {note.type && (
          <Badge variant="outline" className="text-xs shrink-0">
            {note.type.replace(/-/g, ' ')}
          </Badge>
        )}
        <span className="text-sm truncate">{title}</span>
      </button>
      {open && (
        <div className="px-4 py-3 border-t border-border/40 bg-card/50">
          <div className="prose prose-sm dark:prose-invert max-w-none">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>{note.content}</ReactMarkdown>
          </div>
        </div>
      )}
    </div>
  );
}

export default function SystemPage({ params }: SystemPageProps) {
  const { id } = use(params);
  const vm = useSystemViewModel(id);

  if (vm.loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <RefreshCw className="w-8 h-8 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (vm.error || !vm.system) {
    return (
      <div className="min-h-screen p-8">
        <Link href="/techrecon">
          <Button variant="ghost" className="mb-4">
            <ArrowLeft className="w-4 h-4 mr-2" />
            Back to TechRecon
          </Button>
        </Link>
        <div className="bg-destructive/10 text-destructive px-4 py-3 rounded-lg">
          <strong>Error:</strong> {vm.error || 'System not found'}
        </div>
      </div>
    );
  }

  const { system, components, architectureNote, assessmentNote, otherNotes,
          literaturePapers, benchmarks, decisions, workflows, artifacts, tags } = vm;

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const comps = components as any[];
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const benches = benchmarks as any[];
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const decs = decisions as any[];
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const wfs = workflows as any[];
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const arts = artifacts as any[];

  return (
    <div className="min-h-screen">
      {/* Header / Dossier Cover */}
      <header className="border-b border-border/50 bg-card/50 backdrop-blur-sm">
        <div className="container mx-auto px-4 py-4">
          <Link href="/techrecon" className={`flex items-center gap-2 text-sm mb-3 ${linkClass}`}>
            <ArrowLeft className="w-4 h-4" />
            TechRecon
          </Link>
          <div className="flex items-start justify-between gap-4">
            <div className="flex-1">
              <h1 className="text-2xl font-bold bg-gradient-to-r from-cyan-400 to-blue-400 bg-clip-text text-transparent">
                {system.name || 'Unknown System'}
              </h1>
              {system.description && (
                <p className="text-sm text-muted-foreground mt-1 max-w-2xl">
                  {system.description}
                </p>
              )}
              {/* Metadata strip */}
              <div className="flex flex-wrap items-center gap-3 mt-2 text-xs text-muted-foreground">
                {system.repo_url && (
                  <a
                    href={system.repo_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className={`flex items-center gap-1 ${linkClass} text-xs`}
                  >
                    <ExternalLink className="w-3 h-3" />
                    Repository
                  </a>
                )}
                {system.version && (
                  <span className="flex items-center gap-1">
                    <Package className="w-3 h-3" />
                    v{system.version}
                  </span>
                )}
                {system.license && (
                  <span className="flex items-center gap-1">
                    <Scale className="w-3 h-3" />
                    {system.license}
                  </span>
                )}
                {system.stars != null && system.stars > 0 && (
                  <span className="flex items-center gap-1">
                    <Star className="w-3 h-3 text-amber-400" />
                    {system.stars.toLocaleString()}
                  </span>
                )}
                {system.last_commit && (
                  <span className="flex items-center gap-1">
                    <GitBranch className="w-3 h-3" />
                    Last commit: {system.last_commit}
                  </span>
                )}
                {system.base_model && (
                  <span className="flex items-center gap-1">
                    <Brain className="w-3 h-3 text-purple-400" />
                    {system.base_model}
                  </span>
                )}
              </div>
            </div>
            <div className="flex items-center gap-2 shrink-0">
              {system.language && <LanguageBadge language={system.language} />}
              {system.maturity && <MaturityBadge maturity={system.maturity} />}
            </div>
          </div>
          {tags.length > 0 && (
            <div className="flex items-center gap-2 flex-wrap mt-3">
              <TagChips tags={tags} />
            </div>
          )}
        </div>
      </header>

      <main className="container mx-auto px-4 py-6 space-y-6">
        {/* Architecture — top narrative section */}
        <section>
          <h2 className="text-xs font-semibold uppercase tracking-widest text-muted-foreground mb-3 flex items-center gap-2">
            <Puzzle className="w-3.5 h-3.5" />
            Architecture
          </h2>
          {architectureNote ? (
            <div className="prose prose-sm dark:prose-invert max-w-none bg-card/30 rounded-lg p-4 border border-border/40">
              <ReactMarkdown remarkPlugins={[remarkGfm]}>{architectureNote.content}</ReactMarkdown>
            </div>
          ) : (
            <div className="text-sm text-muted-foreground italic bg-card/20 rounded-lg p-4 border border-dashed border-border/40">
              No architecture note yet. Use{' '}
              <code className="text-xs bg-muted px-1 py-0.5 rounded">
                techrecon add-note --type architecture
              </code>{' '}
              to document the system architecture.
            </div>
          )}

          {/* Components grid */}
          {comps.length > 0 && (
            <div className="mt-4 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
              {comps.map((c) => (
                <Link
                  key={c.id}
                  href={`/techrecon/component/${c.id}`}
                  className="block p-3 rounded-lg border border-border/50 bg-card/30 hover:border-primary/50 hover:bg-card/60 transition-all"
                >
                  <p className={`text-sm font-medium ${linkClass}`}>{c.name}</p>
                  {c.role && (
                    <p className="text-xs text-muted-foreground mt-0.5 line-clamp-2">{c.role}</p>
                  )}
                  {c.type && (
                    <Badge variant="outline" className="text-xs mt-1">
                      {c.type}
                    </Badge>
                  )}
                </Link>
              ))}
            </div>
          )}
        </section>

        {/* Evidence — Literature + Benchmarks (2-col) */}
        {(literaturePapers.length > 0 || benches.length > 0) && (
          <section>
            <h2 className="text-xs font-semibold uppercase tracking-widest text-muted-foreground mb-3">
              Evidence
            </h2>
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              {/* Literature */}
              <div>
                <h3 className="text-sm font-semibold mb-2 flex items-center gap-2">
                  <BookOpen className="w-4 h-4 text-muted-foreground" />
                  Literature
                  {literaturePapers.length > 0 && (
                    <Badge variant="secondary" className="ml-1 text-xs">
                      {literaturePapers.length}
                    </Badge>
                  )}
                </h3>
                <LiteratureList papers={literaturePapers} emptyMessage="No literature linked." />
              </div>

              {/* Performance */}
              {benches.length > 0 && (
                <div>
                  <h3 className="text-sm font-semibold mb-2 flex items-center gap-2">
                    <BarChart2 className="w-4 h-4 text-muted-foreground" />
                    Performance
                    <Badge variant="secondary" className="ml-1 text-xs">
                      {benches.length}
                    </Badge>
                  </h3>
                  <div className="overflow-x-auto rounded-lg border border-border/50">
                    <table className="w-full text-sm">
                      <thead>
                        <tr className="border-b border-border/50 bg-muted/20">
                          <th className="text-left px-3 py-2 font-medium text-muted-foreground">
                            Benchmark
                          </th>
                          <th className="text-right px-3 py-2 font-medium text-muted-foreground">
                            Value
                          </th>
                        </tr>
                      </thead>
                      <tbody>
                        {benches.map((b, idx) => (
                          <tr
                            key={b.id || idx}
                            className="border-b border-border/30 last:border-0"
                          >
                            <td className="px-3 py-2">
                              <span className="font-medium">{b.name}</span>
                              {b.metric && b.metric !== b.name && (
                                <span className="text-muted-foreground ml-1 text-xs">
                                  ({b.metric})
                                </span>
                              )}
                            </td>
                            <td className="px-3 py-2 text-right font-mono text-xs">
                              {b.value}
                              {b.unit && (
                                <span className="text-muted-foreground ml-0.5">{b.unit}</span>
                              )}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}
            </div>
          </section>
        )}

        {/* Design Decisions */}
        {decs.length > 0 && (
          <section>
            <h2 className="text-xs font-semibold uppercase tracking-widest text-muted-foreground mb-3 flex items-center gap-2">
              <GitBranch className="w-3.5 h-3.5" />
              Design decisions
            </h2>
            <div className="space-y-2">
              {decs.map((d, idx) => (
                <div key={d.id || idx} className="p-3 rounded-lg bg-muted/30 border border-border/40 space-y-1.5">
                  <div className="flex items-center gap-2">
                    <span className="font-medium text-sm">{d.name}</span>
                    {d.status && (
                      <Badge variant="outline" className="text-xs capitalize ml-auto">
                        {d.status}
                      </Badge>
                    )}
                  </div>
                  {d.rationale && (
                    <p className="text-xs text-muted-foreground">
                      <strong>Rationale:</strong> {d.rationale}
                    </p>
                  )}
                  {d['alternatives'] && (
                    <p className="text-xs text-muted-foreground">
                      <strong>Alternatives:</strong> {d['alternatives']}
                    </p>
                  )}
                  {d['trade-off'] && (
                    <p className="text-xs text-muted-foreground">
                      <strong>Trade-off:</strong> {d['trade-off']}
                    </p>
                  )}
                </div>
              ))}
            </div>
          </section>
        )}

        {/* Assessment — conclusion section */}
        <section>
          <h2 className="text-xs font-semibold uppercase tracking-widest text-muted-foreground mb-3">
            Assessment
          </h2>
          {assessmentNote ? (
            <div className="prose prose-sm dark:prose-invert max-w-none bg-primary/5 rounded-lg p-4 border border-primary/20">
              <ReactMarkdown remarkPlugins={[remarkGfm]}>{assessmentNote.content}</ReactMarkdown>
            </div>
          ) : (
            <div className="text-sm text-muted-foreground italic bg-card/20 rounded-lg p-4 border border-dashed border-border/40">
              No assessment yet. Use{' '}
              <code className="text-xs bg-muted px-1 py-0.5 rounded">
                techrecon add-note --type assessment
              </code>{' '}
              to record your evaluation.
            </div>
          )}
        </section>

        {/* Raw Materials — collapsed */}
        {(arts.length > 0 || otherNotes.length > 0 || wfs.length > 0) && (
          <section>
            <h2 className="text-xs font-semibold uppercase tracking-widest text-muted-foreground mb-3">
              Raw materials
            </h2>
            <div className="space-y-2">
              {wfs.length > 0 && (
                <CollapsibleSection
                  title="Workflows"
                  count={wfs.length}
                  icon={Workflow}
                >
                  <div className="space-y-2">
                    {wfs.map((wf) => (
                      <div key={wf.id} className="flex items-center justify-between text-sm">
                        <Link href={`/techrecon/workflow/${wf.id}`} className={linkClass}>
                          {wf.name}
                        </Link>
                        <GranularityBadge granularity={wf.granularity} />
                      </div>
                    ))}
                  </div>
                </CollapsibleSection>
              )}
              {arts.length > 0 && (
                <CollapsibleSection
                  title="Artifacts"
                  count={arts.length}
                  icon={FileText}
                >
                  <div className="space-y-1">
                    {arts.map((a) => (
                      <Link
                        key={a.id}
                        href={`/techrecon/artifact/${a.id}`}
                        className={`flex items-center gap-2 text-sm py-1 ${linkClass}`}
                      >
                        <span className="truncate">{a.name}</span>
                        {a.type && <TypeBadge type={a.type} />}
                      </Link>
                    ))}
                  </div>
                </CollapsibleSection>
              )}
              {otherNotes.length > 0 && (
                <CollapsibleSection
                  title="Other notes"
                  count={otherNotes.length}
                  icon={Database}
                >
                  <div className="space-y-1.5">
                    {otherNotes.map((n) => (
                      <NoteCard key={n.id} note={n} />
                    ))}
                  </div>
                </CollapsibleSection>
              )}
              {tags.length > 0 && (
                <div className="flex items-center gap-2 flex-wrap px-2 pt-1">
                  <span className="text-xs text-muted-foreground">Tags:</span>
                  <TagChips tags={tags} />
                </div>
              )}
            </div>
          </section>
        )}
      </main>
    </div>
  );
}
