'use client';

import { useState, useEffect, useCallback, use } from 'react';
import Link from 'next/link';
import { RefreshCw, ArrowLeft, GitCommit, FlaskConical, AlertTriangle, Lightbulb } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { PhaseOverview } from '@/components/skill-builder/phase-overview';
import { GapsList } from '@/components/skill-builder/gaps-list';
import { DecisionsList } from '@/components/skill-builder/decisions-list';
import type { Gap } from '@/components/skill-builder/gaps-list';
import type { Decision } from '@/components/skill-builder/decisions-list';

interface Goal {
  id: string;
  name: string;
  description?: string;
}

interface Version {
  id: string;
  tag?: string;
  commit?: string;
  branch?: string;
  message?: string;
  created?: string;
}

interface DomainDetail {
  domain: {
    id: string;
    name: string;
    description?: string;
    skill?: string;
    task?: string;
    created?: string;
  };
  versions: Version[];
  decisions: Decision[];
  experiments: unknown[];
  errors: unknown[];
  goals: Goal[];
  phase_items: Record<string, { id: string; name: string; feasibility?: string; phase?: number }[]>;
  open_gap_counts_by_phase: Record<string, number>;
}

interface GapsResponse {
  gaps: Gap[];
}

function formatDate(iso?: string) {
  if (!iso) return '';
  return new Date(iso.replace('.000000000', '')).toLocaleDateString('en-US', {
    month: 'short', day: 'numeric', year: 'numeric',
  });
}

export default function DomainDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const [detail, setDetail] = useState<DomainDetail | null>(null);
  const [gaps, setGaps] = useState<Gap[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [detailRes, gapsRes] = await Promise.all([
        fetch(`/api/skill-builder/domain/${id}`),
        fetch(`/api/skill-builder/domain/${id}/gaps`),
      ]);
      if (!detailRes.ok) throw new Error('Failed to fetch domain');
      const detailData: DomainDetail = await detailRes.json();
      setDetail(detailData);
      if (gapsRes.ok) {
        const gapsData: GapsResponse = await gapsRes.json();
        setGaps(gapsData.gaps ?? []);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load data');
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => { fetchData(); }, [fetchData]);

  const domain = detail?.domain;
  const totalGaps = gaps.filter(g => g.status === 'open').length;
  const criticalGaps = gaps.filter(g => g.status === 'open' && g.severity === 'critical').length;

  return (
    <div className="min-h-screen">
      <header className="border-b border-border/50 bg-card/50 backdrop-blur-sm">
        <div className="container mx-auto px-4 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-6">
              <Link
                href="/skill-builder"
                className="flex items-center gap-2 text-sm text-muted-foreground hover:text-primary transition-colors"
              >
                <ArrowLeft className="w-4 h-4" />
                Domain Modeling
              </Link>
              <div>
                <h1 className="text-2xl font-bold bg-gradient-to-r from-violet-400 to-purple-400 bg-clip-text text-transparent">
                  {loading ? 'Loading…' : (domain?.name ?? id)}
                </h1>
                {domain?.skill && (
                  <p className="text-sm text-muted-foreground font-mono">skill: {domain.skill}</p>
                )}
              </div>
            </div>
            <Button
              variant="outline"
              size="sm"
              onClick={fetchData}
              disabled={loading}
              className="border-border/50 hover:border-violet-500/50 hover:bg-violet-500/10"
            >
              <RefreshCw className={`w-4 h-4 mr-2 ${loading ? 'animate-spin' : ''}`} />
              Refresh
            </Button>
          </div>
        </div>
      </header>

      <main className="container mx-auto px-4 py-6 space-y-8">
        {error && (
          <div className="bg-destructive/10 text-destructive px-4 py-3 rounded-lg">
            <strong>Error:</strong> {error}
          </div>
        )}

        {loading && (
          <div className="flex items-center justify-center py-12">
            <RefreshCw className="w-6 h-6 animate-spin text-muted-foreground" />
          </div>
        )}

        {!loading && detail && (
          <>
            {/* Description + task */}
            {(domain?.description || domain?.task) && (
              <div className="rounded-xl border border-border/40 bg-card/30 p-5 space-y-2">
                {domain?.description && (
                  <p className="text-sm text-foreground/80 leading-relaxed">{domain.description}</p>
                )}
                {domain?.task && (
                  <p className="text-sm text-muted-foreground italic border-t border-border/30 pt-2">
                    <span className="font-medium not-italic text-muted-foreground/70">Task: </span>
                    {domain.task}
                  </p>
                )}
              </div>
            )}

            {/* Stats bar */}
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
              <StatCard
                value={totalGaps}
                label="Open Gaps"
                warn={criticalGaps > 0}
                icon={<AlertTriangle className="w-4 h-4" />}
              />
              <StatCard
                value={detail.decisions.length}
                label="Decisions"
                icon={<Lightbulb className="w-4 h-4" />}
              />
              <StatCard
                value={detail.versions.length}
                label="Snapshots"
                icon={<GitCommit className="w-4 h-4" />}
              />
              <StatCard
                value={detail.experiments.length}
                label="Experiments"
                icon={<FlaskConical className="w-4 h-4" />}
              />
            </div>

            {/* Phase overview */}
            <Section title="Design Phases">
              <PhaseOverview
                phaseItems={detail.phase_items}
                goals={detail.goals}
                openGapCountsByPhase={detail.open_gap_counts_by_phase}
              />
            </Section>

            {/* Open gaps */}
            {gaps.length > 0 && (
              <Section
                title="Open Gaps"
                count={totalGaps}
                countClassName={criticalGaps > 0 ? 'text-red-400' : 'text-orange-400'}
              >
                <GapsList gaps={gaps.filter(g => g.status === 'open')} />
              </Section>
            )}

            {/* Decisions */}
            {detail.decisions.length > 0 && (
              <Section title="Design Decisions" count={detail.decisions.length}>
                <DecisionsList decisions={detail.decisions} />
              </Section>
            )}

            {/* Snapshots */}
            {detail.versions.length > 0 && (
              <Section title="Skill Snapshots" count={detail.versions.length}>
                <div className="space-y-2">
                  {detail.versions.map((v) => (
                    <div key={v.id} className="rounded-lg border border-border/40 bg-card/30 p-3 flex flex-wrap items-start gap-3">
                      <div className="flex-1 min-w-0">
                        {v.tag && (
                          <span className="text-xs font-mono text-violet-300 bg-violet-500/10 px-2 py-0.5 rounded mr-2">
                            {v.tag}
                          </span>
                        )}
                        {v.message && (
                          <span className="text-sm text-foreground/80">{v.message}</span>
                        )}
                        {v.commit && (
                          <p className="text-xs font-mono text-muted-foreground mt-1">{v.commit.slice(0, 12)}</p>
                        )}
                      </div>
                      {v.created && (
                        <span className="text-xs text-muted-foreground flex-shrink-0">{formatDate(v.created)}</span>
                      )}
                    </div>
                  ))}
                </div>
              </Section>
            )}
          </>
        )}
      </main>

      <footer className="border-t border-border/50 mt-8">
        <div className="container mx-auto px-4 py-4">
          <p className="text-xs text-muted-foreground text-center">
            Domain Modeling &bull; Powered by TypeDB + Next.js
          </p>
        </div>
      </footer>
    </div>
  );
}

function Section({
  title,
  count,
  countClassName,
  children,
}: {
  title: string;
  count?: number;
  countClassName?: string;
  children: React.ReactNode;
}) {
  return (
    <div>
      <div className="flex items-center gap-2 mb-3">
        <h2 className="text-base font-semibold text-foreground">{title}</h2>
        {count != null && (
          <span className={`text-sm ${countClassName ?? 'text-muted-foreground'}`}>({count})</span>
        )}
      </div>
      {children}
    </div>
  );
}

function StatCard({
  value,
  label,
  warn,
  icon,
}: {
  value: number;
  label: string;
  warn?: boolean;
  icon: React.ReactNode;
}) {
  return (
    <div className={`rounded-lg border p-4 ${warn ? 'border-red-500/30 bg-red-500/5' : 'border-border/40 bg-card/30'}`}>
      <div className={`flex items-center gap-2 mb-1 ${warn ? 'text-red-400' : 'text-muted-foreground'}`}>
        {icon}
        <span className="text-xs">{label}</span>
      </div>
      <div className={`text-2xl font-bold ${warn && value > 0 ? 'text-red-400' : 'text-foreground'}`}>
        {value}
      </div>
    </div>
  );
}
