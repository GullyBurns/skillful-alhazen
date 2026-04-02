'use client';

import { useState, useEffect, use } from 'react';
import Link from 'next/link';
import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { StageIndicator } from '@/components/tech-recon/stage-indicator';
import { SystemsGrid } from '@/components/tech-recon/systems-grid';
import { NotesList } from '@/components/tech-recon/notes-list';
import { ReportContent } from '@/components/tech-recon/report-content';
import {
  ArrowLeft,
  RefreshCw,
  Target,
  CheckSquare,
  BarChart2,
  StickyNote,
  BarChart,
  FileText,
  ClipboardCheck,
} from 'lucide-react';
import type { Investigation, TechReconSystem, TechReconNote, TechReconAnalysis } from '@/lib/tech-recon';

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

const ANALYSIS_TYPE_COLORS: Record<string, string> = {
  comparison: 'bg-blue-500/20 text-blue-400 border-blue-500/30',
  trend: 'bg-purple-500/20 text-purple-400 border-purple-500/30',
  distribution: 'bg-amber-500/20 text-amber-400 border-amber-500/30',
  ranking: 'bg-cyan-500/20 text-cyan-400 border-cyan-500/30',
};

function getAnalysisTypeColor(type: string | null | undefined): string {
  if (!type) return 'bg-slate-500/20 text-slate-300 border-slate-500/30';
  return ANALYSIS_TYPE_COLORS[type.toLowerCase()] || 'bg-slate-500/20 text-slate-300 border-slate-500/30';
}

interface PageData {
  investigation: Investigation;
  systems: TechReconSystem[];
  notes: TechReconNote[];
  analyses: TechReconAnalysis[];
}

interface InvestigationPageProps {
  params: Promise<{ id: string }>;
}

export default function InvestigationPage({ params }: InvestigationPageProps) {
  const { id } = use(params);
  const [data, setData] = useState<PageData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<'report' | 'analyses' | 'viz-plan' | 'notes' | 'completion'>('report');

  const fetchData = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`/api/tech-recon/investigation/${id}`);
      if (!res.ok) throw new Error(`API error: ${res.status}`);
      const json = await res.json();
      setData(json);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchData(); }, [id]);

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <RefreshCw className="w-6 h-6 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="min-h-screen">
        <header className="border-b border-border/50 bg-card/50 backdrop-blur-sm">
          <div className="container mx-auto px-4 py-4">
            <Link href="/tech-recon" className={`flex items-center gap-2 text-sm ${linkClass}`}>
              <ArrowLeft className="w-4 h-4" />
              Back to Tech Recon
            </Link>
          </div>
        </header>
        <main className="container mx-auto px-4 py-12 text-center">
          <p className="text-destructive">{error || 'Investigation not found'}</p>
        </main>
      </div>
    );
  }

  const { investigation, systems, notes, analyses } = data;
  const allNotes = notes;

  // Separate special notes from others
  const vizPlanNotes = allNotes.filter((n) => n.topic === 'viz-plan');
  const synthesisNote = allNotes.find((n) => n.topic === 'synthesis-report') ?? null;
  const completionNote = allNotes.find((n) => n.topic === 'completion-assessment') ?? null;
  const otherNotes = allNotes.filter(
    (n) => !['viz-plan', 'synthesis-report', 'completion-assessment'].includes(n.topic)
  );

  return (
    <div className="min-h-screen">
      {/* Header */}
      <header className="border-b border-border/50 bg-card/50 backdrop-blur-sm">
        <div className="container mx-auto px-4 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-6">
              <Link href="/tech-recon" className={`flex items-center gap-2 text-sm ${linkClass}`}>
                <ArrowLeft className="w-4 h-4" />
                Tech Recon
              </Link>
              <div>
                <div className="flex items-center gap-3">
                  <h1 className="text-2xl font-bold bg-gradient-to-r from-cyan-400 to-blue-400 bg-clip-text text-transparent">
                    {investigation.name}
                  </h1>
                  {investigation.status && (
                    <Badge className={`${getStatusColor(investigation.status)} text-xs`}>
                      {investigation.status}
                    </Badge>
                  )}
                  {completionNote
                    ? <Badge className="bg-emerald-500/20 text-emerald-400 border-emerald-500/30 text-xs">Assessed</Badge>
                    : <Badge className="bg-amber-500/20 text-amber-400 border-amber-500/30 text-xs">Not evaluated</Badge>
                  }
                </div>
              </div>
            </div>
            <Button
              variant="outline"
              size="sm"
              onClick={fetchData}
              className="border-border/50 hover:border-primary/50 hover:bg-primary/10"
            >
              <RefreshCw className="w-4 h-4 mr-2" />
              Refresh
            </Button>
          </div>
        </div>
      </header>

      {/* Stage Indicator */}
      <div className="border-b border-border/50 bg-card/20">
        <div className="container mx-auto px-4">
          <StageIndicator status={investigation.status || 'scoping'} />
        </div>
      </div>

      <main className="container mx-auto px-4 py-6 space-y-6">
        {/* Goal Section — always visible */}
        <section>
          <h2 className="text-xs font-semibold uppercase tracking-widest text-muted-foreground mb-3">
            Investigation Goal
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {investigation.goal && (
              <Card className="border-border/50 bg-card/30">
                <CardContent className="pt-4">
                  <div className="flex items-start gap-2">
                    <Target className="w-4 h-4 mt-0.5 text-cyan-400 shrink-0" />
                    <div>
                      <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-1">
                        Goal
                      </p>
                      <p className="text-sm">{investigation.goal}</p>
                    </div>
                  </div>
                </CardContent>
              </Card>
            )}
            {investigation.criteria && (
              <Card className="border-border/50 bg-card/30">
                <CardContent className="pt-4">
                  <div className="flex items-start gap-2">
                    <CheckSquare className="w-4 h-4 mt-0.5 text-green-400 shrink-0" />
                    <div>
                      <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-1">
                        Success Criteria
                      </p>
                      <p className="text-sm">{investigation.criteria}</p>
                    </div>
                  </div>
                </CardContent>
              </Card>
            )}
          </div>
        </section>

        {/* Systems Grid */}
        <section>
          <h2 className="text-xs font-semibold uppercase tracking-widest text-muted-foreground mb-3">
            Systems under investigation
          </h2>
          <SystemsGrid systems={systems} investigationId={id} />
        </section>

        {/* Tabs: Report | Analyses | Viz Plan | Notes | Completion */}
        <section>
          <div className="flex gap-1 border-b border-border/50 mb-4 overflow-x-auto">
            {([
              { key: 'report', label: 'Report', icon: FileText },
              { key: 'analyses', label: 'Analyses', icon: BarChart2 },
              { key: 'viz-plan', label: 'Viz Plan', icon: BarChart },
              { key: 'notes', label: 'Notes', icon: StickyNote },
              { key: 'completion', label: 'Completion', icon: ClipboardCheck },
            ] as const).map(({ key, label, icon: Icon }) => (
              <button
                key={key}
                onClick={() => setActiveTab(key)}
                className={`flex items-center gap-1.5 px-4 py-2 text-sm font-medium border-b-2 transition-colors whitespace-nowrap ${
                  activeTab === key
                    ? 'border-cyan-400 text-cyan-400'
                    : 'border-transparent text-muted-foreground hover:text-foreground'
                }`}
              >
                <Icon className="w-3.5 h-3.5" />
                {label}
                {key === 'analyses' && analyses.length > 0 && (
                  <Badge variant="secondary" className="text-xs ml-1">
                    {analyses.length}
                  </Badge>
                )}
                {key === 'notes' && otherNotes.length > 0 && (
                  <Badge variant="secondary" className="text-xs ml-1">
                    {otherNotes.length}
                  </Badge>
                )}
              </button>
            ))}
          </div>

          {/* Report Tab */}
          {activeTab === 'report' && (
            <div>
              {!synthesisNote ? (
                <div className="space-y-3">
                  <p className="text-sm text-muted-foreground italic">No synthesis report yet. Run:</p>
                  <pre className="text-xs bg-muted/50 border border-border/40 rounded p-3 whitespace-pre-wrap">
                    {`uv run python .claude/skills/tech-recon/tech_recon.py compile-report --investigation ${id}`}
                  </pre>
                  <p className="text-xs text-muted-foreground">
                    Then ask Claude to write the synthesis report using the returned context.
                  </p>
                </div>
              ) : (
                <div className="space-y-2">
                  <p className="text-xs text-muted-foreground">Note: {synthesisNote.id}</p>
                  <ReportContent noteId={synthesisNote.id} preview={synthesisNote.content_preview} />
                </div>
              )}
            </div>
          )}

          {/* Analyses Tab */}
          {activeTab === 'analyses' && (
            <div>
              {analyses.length === 0 ? (
                <p className="text-sm text-muted-foreground italic">
                  No analyses planned yet. Use{' '}
                  <code className="text-xs bg-muted px-1 py-0.5 rounded">
                    tech-recon plan-analyses
                  </code>{' '}
                  to generate analysis plans.
                </p>
              ) : (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                  {analyses.map((analysis) => (
                    <div
                      key={analysis.id}
                      className="border border-border/50 rounded-lg bg-card/30 p-3 space-y-2"
                    >
                      <div className="flex items-start justify-between gap-2">
                        <Link
                          href={`/tech-recon/investigation/${id}/analysis/${analysis.id}`}
                          className={`text-sm font-medium ${linkClass}`}
                        >
                          {analysis.title}
                        </Link>
                        {analysis.type && (
                          <Badge className={`${getAnalysisTypeColor(analysis.type)} text-xs shrink-0`}>
                            {analysis.type}
                          </Badge>
                        )}
                      </div>
                      {analysis.description && (
                        <p className="text-xs text-muted-foreground line-clamp-2">
                          {analysis.description}
                        </p>
                      )}
                      <Link
                        href={`/tech-recon/investigation/${id}/analysis/${analysis.id}`}
                      >
                        <Button variant="outline" size="sm" className="text-xs h-7 mt-1">
                          <BarChart2 className="w-3 h-3 mr-1" />
                          Run
                        </Button>
                      </Link>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* Viz Plan Tab */}
          {activeTab === 'viz-plan' && (
            <div>
              {vizPlanNotes.length === 0 ? (
                <p className="text-sm text-muted-foreground italic">
                  No viz plan yet. Use{' '}
                  <code className="text-xs bg-muted px-1 py-0.5 rounded">
                    tech-recon plan-analyses
                  </code>{' '}
                  to generate a visualization plan.
                </p>
              ) : (
                <div className="space-y-4">
                  {vizPlanNotes.map((note) => (
                    <div key={note.id}>
                      <pre className="text-xs rounded-lg bg-muted/50 border border-border/40 p-4 overflow-x-auto whitespace-pre-wrap">
                        <code>{note.content}</code>
                      </pre>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* Notes Tab */}
          {activeTab === 'notes' && (
            <NotesList notes={otherNotes} />
          )}

          {/* Completion Tab */}
          {activeTab === 'completion' && (
            <div>
              {!completionNote ? (
                <div className="space-y-3">
                  <p className="text-sm text-muted-foreground italic">No completion assessment yet. Run:</p>
                  <pre className="text-xs bg-muted/50 border border-border/40 rounded p-3 whitespace-pre-wrap">
                    {`uv run python .claude/skills/tech-recon/tech_recon.py evaluate-completion --investigation ${id}`}
                  </pre>
                  <p className="text-xs text-muted-foreground">
                    Then ask Claude to write the completion assessment using the returned context.
                  </p>
                </div>
              ) : (
                <div className="space-y-2">
                  <p className="text-xs text-muted-foreground">Note: {completionNote.id}</p>
                  <ReportContent noteId={completionNote.id} preview={completionNote.content_preview} />
                </div>
              )}
            </div>
          )}
        </section>
      </main>

      <footer className="border-t border-border/50 mt-8">
        <div className="container mx-auto px-4 py-4">
          <p className="text-xs text-muted-foreground text-center">
            Tech Recon &bull; Powered by TypeDB + Next.js
          </p>
        </div>
      </footer>
    </div>
  );
}
