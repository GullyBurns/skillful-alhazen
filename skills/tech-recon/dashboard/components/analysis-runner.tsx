'use client';

import { useState, useRef, useEffect } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Play, RefreshCw, BarChart2, Table, FileText } from 'lucide-react';

const ANALYSIS_TYPE_COLORS: Record<string, string> = {
  comparison: 'bg-blue-500/20 text-blue-400 border-blue-500/30',
  trend: 'bg-purple-500/20 text-purple-400 border-purple-500/30',
  distribution: 'bg-amber-500/20 text-amber-400 border-amber-500/30',
  ranking: 'bg-cyan-500/20 text-cyan-400 border-cyan-500/30',
  plot: 'bg-green-500/20 text-green-400 border-green-500/30',
  table: 'bg-yellow-500/20 text-yellow-400 border-yellow-500/30',
  prose: 'bg-indigo-500/20 text-indigo-400 border-indigo-500/30',
};

function getAnalysisTypeColor(type: string | null | undefined): string {
  if (!type) return 'bg-slate-500/20 text-slate-300 border-slate-500/30';
  return ANALYSIS_TYPE_COLORS[type.toLowerCase()] || 'bg-slate-500/20 text-slate-300 border-slate-500/30';
}

function getAnalysisTypeIcon(type: string | null | undefined) {
  const t = (type || '').toLowerCase();
  if (t === 'prose') return <FileText className="w-3.5 h-3.5" />;
  if (t === 'table') return <Table className="w-3.5 h-3.5" />;
  return <BarChart2 className="w-3.5 h-3.5" />;
}

export interface AnalysisRunnerProps {
  analysisId: string;
  title: string;
  description?: string;
  analysisType: string; // 'plot' | 'table' | 'prose'
}

// PlotContainer mounts an Observable Plot element into the DOM
function PlotContainer({ plotCode, data }: { plotCode: string; data: unknown[] }) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!containerRef.current) return;

    let cancelled = false;

    (async () => {
      try {
        // Dynamic import so the bundle stays clean; falls back gracefully if unavailable
        const Plot = await import('@observablehq/plot');
        if (cancelled) return;

        // plot_code is a JS expression, e.g.:
        //   Plot.plot({ marks: [Plot.barY(data, {x: 'name', y: 'value'})] })
        // eslint-disable-next-line no-new-func
        const plotEl = new Function('Plot', 'data', `return ${plotCode}`)(Plot, data);

        if (cancelled || !containerRef.current) return;
        containerRef.current.replaceChildren(plotEl);
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : String(err));
        }
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [plotCode, data]);

  if (error) {
    return (
      <div className="bg-destructive/10 text-destructive px-4 py-3 rounded-lg text-sm">
        <strong>Plot render error:</strong> {error}
      </div>
    );
  }

  return (
    <div
      ref={containerRef}
      className="overflow-x-auto rounded-lg bg-white dark:bg-slate-900 p-4 border border-border/40"
    />
  );
}

export function AnalysisRunner({
  analysisId,
  title,
  description,
  analysisType,
}: AnalysisRunnerProps) {
  const [running, setRunning] = useState(false);
  const [runError, setRunError] = useState<string | null>(null);
  const [plotCode, setPlotCode] = useState<string | null>(null);
  const [data, setData] = useState<unknown[] | null>(null);
  const [proseContent, setProseContent] = useState<string | null>(null);
  const [hasRun, setHasRun] = useState(false);

  const typeNorm = analysisType?.toLowerCase() || 'plot';

  const handleRun = async () => {
    setRunning(true);
    setRunError(null);
    setPlotCode(null);
    setData(null);
    setProseContent(null);
    setHasRun(false);

    try {
      const res = await fetch(`/api/tech-recon/analysis/${analysisId}/run`);
      if (!res.ok) throw new Error(`Run failed: ${res.status}`);
      const json = await res.json();

      if (json.error) throw new Error(json.error);

      if (typeNorm === 'prose') {
        // For prose analyses the API may return content or a description in data
        setProseContent(
          json.content ||
            (Array.isArray(json.data) && json.data.length > 0
              ? JSON.stringify(json.data, null, 2)
              : description || '')
        );
      } else {
        setPlotCode(json.plot_code || null);
        setData(json.data || []);
      }

      setHasRun(true);
    } catch (err) {
      setRunError(err instanceof Error ? err.message : String(err));
    } finally {
      setRunning(false);
    }
  };

  return (
    <div className="space-y-4">
      {/* Header row: title, type badge, run button */}
      <div className="flex items-start justify-between gap-4">
        <div className="space-y-1.5">
          <div className="flex items-center gap-3 flex-wrap">
            <div className="flex items-center gap-2">
              {getAnalysisTypeIcon(analysisType)}
              <h2 className="text-base font-semibold text-foreground">{title}</h2>
            </div>
            <Badge className={`${getAnalysisTypeColor(analysisType)} text-xs`}>
              {analysisType || 'plot'}
            </Badge>
          </div>
          {description && (
            <p className="text-sm text-muted-foreground max-w-2xl">{description}</p>
          )}
        </div>

        <Button
          onClick={handleRun}
          disabled={running}
          size="sm"
          className="bg-cyan-500/20 text-cyan-400 border border-cyan-500/30 hover:bg-cyan-500/30 shrink-0"
        >
          {running ? (
            <RefreshCw className="w-3.5 h-3.5 mr-1.5 animate-spin" />
          ) : (
            <Play className="w-3.5 h-3.5 mr-1.5" />
          )}
          Run Analysis
        </Button>
      </div>

      {/* Error state */}
      {runError && (
        <div className="bg-destructive/10 text-destructive px-4 py-3 rounded-lg text-sm">
          <strong>Run failed:</strong> {runError}
        </div>
      )}

      {/* Loading state */}
      {running && (
        <div className="flex items-center gap-3 py-8 justify-center text-muted-foreground">
          <RefreshCw className="w-5 h-5 animate-spin" />
          <span className="text-sm">Running analysis&hellip;</span>
        </div>
      )}

      {/* Results */}
      {!running && hasRun && (
        <div className="space-y-4">
          {/* Prose type: render as markdown */}
          {typeNorm === 'prose' && proseContent && (
            <div className="prose prose-sm dark:prose-invert max-w-none rounded-lg bg-card/50 border border-border/40 px-5 py-4">
              <ReactMarkdown remarkPlugins={[remarkGfm]}>{proseContent}</ReactMarkdown>
            </div>
          )}

          {/* Plot / table type: run Observable Plot code */}
          {typeNorm !== 'prose' && plotCode && data !== null && (
            <PlotContainer plotCode={plotCode} data={data} />
          )}

          {/* Fallback: no plot_code returned */}
          {typeNorm !== 'prose' && !plotCode && data !== null && data.length > 0 && (
            <div>
              <h3 className="text-xs font-semibold uppercase tracking-widest text-muted-foreground mb-2">
                Data ({data.length} records)
              </h3>
              <pre className="text-xs rounded-lg bg-muted/50 border border-border/40 p-4 overflow-x-auto max-h-64">
                <code>{JSON.stringify(data, null, 2)}</code>
              </pre>
            </div>
          )}

          {/* Empty result */}
          {typeNorm !== 'prose' && !plotCode && (!data || data.length === 0) && (
            <div className="text-sm text-muted-foreground text-center py-6">
              Analysis returned no data.
            </div>
          )}
        </div>
      )}
    </div>
  );
}
