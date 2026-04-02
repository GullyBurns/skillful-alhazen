'use client';

import { useState, useEffect, use } from 'react';
import Link from 'next/link';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { StageIndicator, type StageCompletion } from '@/components/tech-recon/stage-indicator';
import { SectionNav, type SectionKey, type SectionNavItem, DEFAULT_SECTION_ICONS } from '@/components/tech-recon/section-nav';
import { ScopeSection } from '@/components/tech-recon/discovery-section';
import { SystemsTable } from '@/components/tech-recon/systems-table';
import { SensemakingSection } from '@/components/tech-recon/sources-section';
import { AnalysisSection } from '@/components/tech-recon/visualizations-section';
import { OutputsSection } from '@/components/tech-recon/outputs-section';
import { ArrowLeft, RefreshCw } from 'lucide-react';
import type { Investigation, TechReconSystem, TechReconNote, TechReconAnalysis, TechReconArtifact, SystemData } from '@/lib/tech-recon';

const linkClass =
  'text-cyan-400 font-semibold underline underline-offset-2 hover:text-blue-400 transition-colors';

const STATUS_COLORS: Record<string, string> = {
  active: 'bg-green-500/20 text-green-400 border-green-500/30',
  completed: 'bg-blue-500/20 text-blue-400 border-blue-500/30',
  paused: 'bg-yellow-500/20 text-yellow-400 border-yellow-500/30',
  archived: 'bg-slate-500/20 text-slate-300 border-slate-500/30',
  evaluating: 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30',
  synthesis: 'bg-violet-500/20 text-violet-400 border-violet-500/30',
  done: 'bg-green-500/20 text-green-400 border-green-500/30',
};

function getStatusColor(status: string | null | undefined): string {
  if (!status) return 'bg-slate-500/20 text-slate-300 border-slate-500/30';
  return STATUS_COLORS[status.toLowerCase()] || 'bg-slate-500/20 text-slate-300 border-slate-500/30';
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
  const [activeSection, setActiveSection] = useState<SectionKey>('scope');
  const [systemDataMap, setSystemDataMap] = useState<Record<string, SystemData> | null>(null);
  const [systemDataLoading, setSystemDataLoading] = useState(false);

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

  // Lazy-fetch system artifacts + notes for Discovery, Sensemaking sections
  useEffect(() => {
    if (!['discovery', 'sensemaking'].includes(activeSection) || systemDataMap !== null || !data) return;
    setSystemDataLoading(true);
    Promise.all(
      data.systems.map(s =>
        fetch(`/api/tech-recon/system/${s.id}`)
          .then(r => r.json())
          .then(d => ({
            id: s.id,
            artifacts: (d.artifacts ?? []) as TechReconArtifact[],
            notes: (d.notes ?? []) as TechReconNote[],
          }))
      )
    )
      .then(results => {
        const map: Record<string, SystemData> = {};
        results.forEach(r => { map[r.id] = { artifacts: r.artifacts, notes: r.notes }; });
        setSystemDataMap(map);
      })
      .finally(() => setSystemDataLoading(false));
  }, [activeSection, data, systemDataMap]);

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

  // Derive special investigation-level notes
  const vizPlanNotes = notes.filter(n => n.topic === 'viz-plan');
  const synthesisNote = notes.find(n => n.topic === 'synthesis-report') ?? null;
  const completionNote = notes.find(n => n.topic === 'completion-assessment') ?? null;

  // Compute stage completion (data-driven)
  const totalArtifacts = systems.reduce((s, sys) => s + (sys.artifacts_count ?? 0), 0);
  const totalNotes = systems.reduce((s, sys) => s + (sys.notes_count ?? 0), 0);
  const completion: StageCompletion = {
    scope: !!(investigation.goal || investigation.criteria),
    discovery: systems.length > 0,
    sensemaking: totalArtifacts > 0 && totalNotes > 0,
    analysis: analyses.length > 0,
    outputs: synthesisNote !== null,
  };

  // Build sidebar nav items
  const navItems: SectionNavItem[] = [
    { key: 'scope', label: 'Scope', icon: DEFAULT_SECTION_ICONS.scope },
    { key: 'discovery', label: 'Discovery', icon: DEFAULT_SECTION_ICONS.discovery, count: systems.length },
    { key: 'sensemaking', label: 'Sensemaking', icon: DEFAULT_SECTION_ICONS.sensemaking, count: systems.length },
    { key: 'analysis', label: 'Analysis', icon: DEFAULT_SECTION_ICONS.analysis, count: analyses.length },
    {
      key: 'outputs',
      label: 'Outputs',
      icon: DEFAULT_SECTION_ICONS.outputs,
      hasReport: synthesisNote !== null,
      hasAssessment: completionNote !== null,
    },
  ];

  const spinner = (
    <div className="flex justify-center py-12">
      <RefreshCw className="w-5 h-5 animate-spin text-muted-foreground" />
    </div>
  );

  return (
    <div className="min-h-screen flex flex-col">
      {/* Header */}
      <header className="border-b border-border/50 bg-card/50 backdrop-blur-sm">
        <div className="container mx-auto px-4 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-6">
              <Link href="/tech-recon" className={`flex items-center gap-2 text-sm ${linkClass}`}>
                <ArrowLeft className="w-4 h-4" />
                Tech Recon
              </Link>
              <div className="flex items-center gap-3">
                <h1 className="text-2xl font-bold bg-gradient-to-r from-cyan-400 to-blue-400 bg-clip-text text-transparent">
                  {investigation.name}
                </h1>
                {investigation.status && (
                  <Badge className={`${getStatusColor(investigation.status)} text-xs`}>
                    {investigation.status}
                  </Badge>
                )}
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
          <StageIndicator completion={completion} />
        </div>
      </div>

      {/* Main two-column layout */}
      <div className="container mx-auto px-4 py-6 flex gap-6 flex-1">
        <aside className="w-48 shrink-0">
          <div className="sticky top-6">
            <SectionNav items={navItems} active={activeSection} onSelect={setActiveSection} />
          </div>
        </aside>

        <main className="flex-1 min-w-0">
          {activeSection === 'scope' && (
            <ScopeSection investigation={investigation} />
          )}
          {activeSection === 'discovery' && (
            systemDataLoading
              ? spinner
              : <SystemsTable systems={systems} systemDataMap={systemDataMap ?? {}} />
          )}
          {activeSection === 'sensemaking' && (
            systemDataLoading
              ? spinner
              : <SensemakingSection systems={systems} systemDataMap={systemDataMap ?? {}} />
          )}
          {activeSection === 'analysis' && (
            <AnalysisSection analyses={analyses} vizPlanNotes={vizPlanNotes} investigationId={id} />
          )}
          {activeSection === 'outputs' && (
            <OutputsSection synthesisNote={synthesisNote} completionNote={completionNote} investigationId={id} />
          )}
        </main>
      </div>

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
