'use client';

import { useState, useEffect, use } from 'react';
import Link from 'next/link';
import { Badge } from '@/components/ui/badge';
import { ArrowLeft, RefreshCw } from 'lucide-react';
import { AnalysisRunner } from '@/components/tech-recon/analysis-runner';
import type { TechReconAnalysis } from '@/lib/tech-recon';

const linkClass =
  'text-cyan-400 font-semibold underline underline-offset-2 hover:text-blue-400 transition-colors';

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

interface AnalysisPageProps {
  params: Promise<{ id: string; aid: string }>;
}

export default function AnalysisPage({ params }: AnalysisPageProps) {
  const { id, aid } = use(params);
  const [analysis, setAnalysis] = useState<TechReconAnalysis | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchData = async () => {
      setLoading(true);
      setError(null);
      try {
        const res = await fetch(`/api/tech-recon/analysis/${aid}`);
        if (!res.ok) throw new Error(`API error: ${res.status}`);
        const json = await res.json();
        setAnalysis(json.analysis || json);
      } catch (err) {
        setError(err instanceof Error ? err.message : String(err));
      } finally {
        setLoading(false);
      }
    };
    fetchData();
  }, [aid]);

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <RefreshCw className="w-6 h-6 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (error || !analysis) {
    return (
      <div className="min-h-screen p-8">
        <Link
          href={`/tech-recon/investigation/${id}`}
          className={`flex items-center gap-2 text-sm mb-4 ${linkClass}`}
        >
          <ArrowLeft className="w-4 h-4" />
          Back to Investigation
        </Link>
        <div className="bg-destructive/10 text-destructive px-4 py-3 rounded-lg">
          <strong>Error:</strong> {error || 'Analysis not found'}
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen">
      <header className="border-b border-border/50 bg-card/50 backdrop-blur-sm">
        <div className="container mx-auto px-4 py-4">
          <div className="flex items-center gap-3 mb-3 text-sm">
            <Link href="/tech-recon" className={`flex items-center gap-1 ${linkClass}`}>
              <ArrowLeft className="w-4 h-4" />
              Tech Recon
            </Link>
            <span className="text-muted-foreground">/</span>
            <Link href={`/tech-recon/investigation/${id}`} className={linkClass}>
              Investigation
            </Link>
          </div>
          <div className="flex items-center gap-3">
            <h1 className="text-xl font-bold bg-gradient-to-r from-[#5aadaf] to-[#4a7ab5] bg-clip-text text-transparent">
              {analysis.title}
            </h1>
            {analysis.type && (
              <Badge className={`${getAnalysisTypeColor(analysis.type)} text-xs`}>
                {analysis.type}
              </Badge>
            )}
          </div>
        </div>
      </header>

      <main className="container mx-auto px-4 py-6 space-y-6">
        {/* Observable Plot analysis runner */}
        <AnalysisRunner
          analysisId={aid}
          title={analysis.title}
          description={analysis.description}
          plotCode={analysis.plot_code}
          analysisType={analysis.type || 'plot'}
        />

        {/* Static metadata: stored query */}
        {analysis.query && (
          <div>
            <h2 className="text-xs font-semibold uppercase tracking-widest text-muted-foreground mb-3">
              Query
            </h2>
            <pre className="text-xs rounded-lg bg-muted/50 border border-border/40 p-4 overflow-x-auto">
              <code>{analysis.query}</code>
            </pre>
          </div>
        )}
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
