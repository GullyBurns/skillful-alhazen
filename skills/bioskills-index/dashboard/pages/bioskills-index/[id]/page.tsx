'use client';

import { useState, useEffect, useRef, use } from 'react';
import Link from 'next/link';
import * as Plot from '@observablehq/plot';
import {
  Search, Network, Loader2, ExternalLink, Tag, Cpu, Clock, MemoryStick,
  ChevronRight, Database, RefreshCw,
} from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';

// ---------------------------------------------------------------------------
// Design constants
// ---------------------------------------------------------------------------
const linkClass =
  'text-cyan-400 font-semibold underline underline-offset-2 hover:text-blue-400 transition-colors';

const CLUSTER_COLORS = ['#34d399', '#60a5fa', '#f472b6', '#fb923c', '#a78bfa', '#facc15', '#38bdf8', '#e879f9'];

const STAGES = [
  { key: 'setup',       label: 'Setup',       num: 1 },
  { key: 'discovery',   label: 'Discovery',   num: 2 },
  { key: 'annotation',  label: 'Annotation',  num: 3 },
  { key: 'projection',  label: 'Projection',  num: 4 },
  { key: 'search',      label: 'Search & Compose', num: 5 },
] as const;
type Stage = typeof STAGES[number]['key'];

const TOP_EDAM_OPS = [
  { id: 'operation_2403', label: 'Sequence analysis' },
  { id: 'operation_2495', label: 'Expression analysis' },
  { id: 'operation_3197', label: 'Genetic variation analysis' },
  { id: 'operation_0477', label: 'Protein modelling' },
  { id: 'operation_3760', label: 'Service management' },
  { id: 'operation_3200', label: 'Community profiling' },
];

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------
type BsiIndex = {
  id: string; name: string; version: number; skill_count: number;
  status: string; created_at: string;
};

type Skill = {
  id: string; name: string; type: string; status: string;
  cluster_id: number; cluster_label: string;
  umap_x: number; umap_y: number; source_repo: string;
};

type SearchResult = { id: string; name: string; score: number; type: string; source_repo: string };
type PlaylistItem = { rank: number; id: string; name: string; score: number; cluster_id: number; cluster_label: string };

// ---------------------------------------------------------------------------
// Stage dot indicator
// ---------------------------------------------------------------------------
function StageDots({ active }: { active: Stage }) {
  return (
    <div className="flex items-center gap-2 mb-6">
      {STAGES.map((s, i) => (
        <div key={s.key} className="flex items-center gap-2">
          <div className={`w-2.5 h-2.5 rounded-full transition-all ${
            s.key === active ? 'bg-emerald-400 ring-2 ring-emerald-400/30' : 'bg-slate-600'
          }`} />
          {i < STAGES.length - 1 && <div className="w-6 h-px bg-slate-700" />}
        </div>
      ))}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Section: Setup
// ---------------------------------------------------------------------------
function SetupSection({ index, skillCount }: { index: BsiIndex | null; skillCount: number }) {
  if (!index) return <p className="text-muted-foreground">Loading index details...</p>;
  return (
    <div className="space-y-4">
      <div>
        <h2 className="text-xl font-bold mb-1">{index.name}</h2>
        <div className="flex flex-wrap gap-2 mb-3">
          <Badge variant="outline">v{index.version}</Badge>
          <Badge variant="outline" className={index.status === 'active' ? 'text-green-400 border-green-500/30' : 'text-yellow-400 border-yellow-500/30'}>
            {index.status}
          </Badge>
        </div>
        <div className="grid grid-cols-2 gap-4 text-sm">
          <div className="p-3 rounded border border-border bg-muted/20">
            <div className="text-muted-foreground text-xs mb-1">Skills indexed</div>
            <div className="text-2xl font-bold text-emerald-400">{skillCount}</div>
          </div>
          {index.created_at && (
            <div className="p-3 rounded border border-border bg-muted/20">
              <div className="text-muted-foreground text-xs mb-1">Created</div>
              <div className="font-medium">{new Date(index.created_at).toLocaleDateString()}</div>
            </div>
          )}
        </div>
      </div>
      <Card className="border-border">
        <CardContent className="pt-4 text-sm text-muted-foreground space-y-2">
          <p>Discovery sources are configured in <code className="font-mono text-xs bg-muted px-1 rounded">discovery-sources.yaml</code>.
             Run <code className="font-mono text-xs bg-muted px-1 rounded">update --index {index.id}</code> to discover new skills.
          </p>
          <p>Use <code className="font-mono text-xs bg-muted px-1 rounded">embed-and-project --index {index.id}</code> to compute UMAP embeddings and cluster labels.</p>
        </CardContent>
      </Card>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Section: Discovery — all skills table
// ---------------------------------------------------------------------------
const TYPE_COLORS: Record<string, string> = {
  skill: 'text-emerald-400 border-emerald-500/30',
  'mcp-server': 'text-violet-400 border-violet-500/30',
  workflow: 'text-blue-400 border-blue-500/30',
  'python-api': 'text-orange-400 border-orange-500/30',
};

function DiscoverySection({ skills, indexId }: { skills: Skill[]; indexId: string }) {
  const [typeFilter, setTypeFilter] = useState<string>('all');
  const types = ['all', ...Array.from(new Set(skills.map(s => s.type).filter(Boolean)))];
  const filtered = typeFilter === 'all' ? skills : skills.filter(s => s.type === typeFilter);

  const typeCounts = types.reduce<Record<string, number>>((acc, t) => {
    acc[t] = t === 'all' ? skills.length : skills.filter(s => s.type === t).length;
    return acc;
  }, {});

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-3 flex-wrap">
        {types.map(t => (
          <button
            key={t}
            onClick={() => setTypeFilter(t)}
            className={`px-3 py-1 rounded-full text-xs font-medium transition-all border ${
              typeFilter === t
                ? 'bg-emerald-500/20 text-emerald-400 border-emerald-500/50'
                : 'border-border text-muted-foreground hover:border-emerald-500/30'
            }`}
          >
            {t === 'all' ? 'All' : t} <span className="opacity-60 ml-1">{typeCounts[t]}</span>
          </button>
        ))}
      </div>
      <div className="border border-border rounded overflow-hidden">
        <table className="w-full text-sm">
          <thead className="border-b border-border bg-muted/30">
            <tr>
              <th className="px-3 py-2 text-left text-xs font-medium text-muted-foreground">Name</th>
              <th className="px-3 py-2 text-left text-xs font-medium text-muted-foreground">Type</th>
              <th className="px-3 py-2 text-left text-xs font-medium text-muted-foreground">Cluster</th>
              <th className="px-3 py-2 text-left text-xs font-medium text-muted-foreground">Source</th>
            </tr>
          </thead>
          <tbody>
            {filtered.slice(0, 200).map(s => (
              <tr key={s.id} className="border-b border-border/50 hover:bg-muted/20">
                <td className="px-3 py-2">
                  <Link href={`/bioskills-index/${indexId}/skill/${s.id}`} className={linkClass}>
                    {s.name}
                  </Link>
                </td>
                <td className="px-3 py-2">
                  {s.type && (
                    <Badge variant="outline" className={`text-xs ${TYPE_COLORS[s.type] ?? ''}`}>{s.type}</Badge>
                  )}
                </td>
                <td className="px-3 py-2 text-xs text-muted-foreground">{s.cluster_label || '—'}</td>
                <td className="px-3 py-2">
                  {s.source_repo && (
                    <a href={s.source_repo} target="_blank" rel="noopener noreferrer"
                      className="text-xs text-muted-foreground hover:text-foreground flex items-center gap-1">
                      <ExternalLink className="w-3 h-3" />
                    </a>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {filtered.length > 200 && (
          <div className="px-3 py-2 text-xs text-muted-foreground border-t border-border">
            Showing 200 of {filtered.length} skills
          </div>
        )}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Section: Annotation — EDAM coverage
// ---------------------------------------------------------------------------
function AnnotationSection({ indexId, skills }: { indexId: string; skills: Skill[] }) {
  const [opCounts, setOpCounts] = useState<Record<string, number>>({});
  const [loadingCounts, setLoadingCounts] = useState(true);

  useEffect(() => {
    Promise.all(
      TOP_EDAM_OPS.map(op =>
        fetch(`/api/bioskills-index/${indexId}/skills-by-edam?op=${op.id}`)
          .then(r => r.json())
          .then(d => ({ id: op.id, count: (d.skills ?? []).length }))
          .catch(() => ({ id: op.id, count: 0 }))
      )
    ).then(results => {
      const counts: Record<string, number> = {};
      results.forEach(r => { counts[r.id] = r.count; });
      setOpCounts(counts);
      setLoadingCounts(false);
    });
  }, [indexId]);

  return (
    <div className="space-y-5">
      <div className="flex items-center gap-4 text-sm text-muted-foreground">
        <span><strong className="text-foreground">{skills.length}</strong> skills indexed</span>
      </div>
      <div>
        <h3 className="text-sm font-medium mb-3 flex items-center gap-2">
          <Tag className="w-4 h-4 text-emerald-400" /> Top EDAM Operation Categories
        </h3>
        <div className="grid grid-cols-1 gap-2">
          {TOP_EDAM_OPS.map(op => {
            const count = opCounts[op.id] ?? 0;
            const pct = skills.length > 0 ? Math.round((count / skills.length) * 100) : 0;
            return (
              <Link
                key={op.id}
                href={`/bioskills-index/${indexId}/edam/${op.id}`}
                className="flex items-center gap-3 px-3 py-2 rounded border border-border hover:border-emerald-500/30 hover:bg-muted/20 group"
              >
                <div className="flex-1 min-w-0">
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-sm text-emerald-400 group-hover:text-emerald-300">{op.label}</span>
                    <span className="text-xs text-muted-foreground">
                      {loadingCounts ? '...' : count} skills
                    </span>
                  </div>
                  <div className="h-1 bg-muted rounded-full overflow-hidden">
                    <div
                      className="h-full bg-emerald-500/60 rounded-full transition-all"
                      style={{ width: loadingCounts ? '0%' : `${pct}%` }}
                    />
                  </div>
                </div>
                <ChevronRight className="w-3 h-3 text-muted-foreground shrink-0 opacity-0 group-hover:opacity-100" />
              </Link>
            );
          })}
        </div>
        <p className="text-xs text-muted-foreground mt-3">
          Counts include transitive EDAM hierarchy matches.
        </p>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Section: Projection — UMAP scatter
// ---------------------------------------------------------------------------
function ProjectionSection({ skills }: { skills: Skill[] }) {
  const plotRef = useRef<HTMLDivElement>(null);
  const [selectedCluster, setSelectedCluster] = useState<number | null>(null);

  const clusters = [...new Map(skills.map(s => [s.cluster_id, s.cluster_label])).entries()]
    .filter(([cid]) => cid !== -1)
    .sort(([a], [b]) => a - b);

  const clusterIds = [...new Set(skills.map(s => s.cluster_id))].sort();
  const colorScale = Object.fromEntries(
    clusterIds.map((cid, i) => [cid, CLUSTER_COLORS[i % CLUSTER_COLORS.length]])
  );

  useEffect(() => {
    if (!plotRef.current || skills.length === 0) return;
    const filtered = selectedCluster !== null
      ? skills.filter(s => s.cluster_id === selectedCluster)
      : skills;

    const plot = Plot.plot({
      width: plotRef.current.clientWidth || 600,
      height: 420,
      style: { background: 'transparent', color: '#e2e8f0' },
      x: { label: null, ticks: [] },
      y: { label: null, ticks: [] },
      marks: [
        Plot.dot(filtered, {
          x: 'umap_x', y: 'umap_y', r: 4,
          fill: (d: Skill) => colorScale[d.cluster_id] ?? '#6b7280',
          fillOpacity: 0.8,
          title: (d: Skill) => `${d.name}\n${d.cluster_label || `Cluster ${d.cluster_id}`}`,
          tip: true,
        }),
      ],
    });
    plotRef.current.innerHTML = '';
    plotRef.current.appendChild(plot);
    return () => plot.remove();
  }, [skills, selectedCluster]);

  if (skills.length === 0) {
    return (
      <div className="text-center py-16 text-muted-foreground">
        <Network className="w-10 h-10 mx-auto mb-3 opacity-30" />
        <p>No UMAP data. Run <code className="font-mono text-sm">embed-and-project</code> first.</p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap gap-2">
        {clusters.map(([cid, label], i) => (
          <button
            key={cid}
            onClick={() => setSelectedCluster(selectedCluster === cid ? null : cid)}
            className={`flex items-center gap-1.5 px-2 py-1 rounded text-xs transition-all ${
              selectedCluster === cid ? 'ring-1 ring-white/30' : 'opacity-70 hover:opacity-100'
            }`}
            style={{ background: `${CLUSTER_COLORS[i % CLUSTER_COLORS.length]}22`, color: CLUSTER_COLORS[i % CLUSTER_COLORS.length] }}
          >
            <span className="w-2 h-2 rounded-full" style={{ background: CLUSTER_COLORS[i % CLUSTER_COLORS.length] }} />
            {label || `Cluster ${cid}`}
          </button>
        ))}
        {selectedCluster !== null && (
          <button onClick={() => setSelectedCluster(null)} className="text-xs text-muted-foreground hover:text-foreground px-2 py-1">
            Clear filter
          </button>
        )}
      </div>
      <div ref={plotRef} className="w-full" />
      <div className="border border-border rounded overflow-hidden">
        <table className="w-full text-xs">
          <thead className="border-b border-border bg-muted/30">
            <tr>
              <th className="px-3 py-1.5 text-left text-muted-foreground">Cluster</th>
              <th className="px-3 py-1.5 text-right text-muted-foreground">Count</th>
              <th className="px-3 py-1.5 text-right text-muted-foreground">%</th>
            </tr>
          </thead>
          <tbody>
            {clusters.map(([cid, label], i) => {
              const count = skills.filter(s => s.cluster_id === cid).length;
              const pct = ((count / skills.length) * 100).toFixed(1);
              return (
                <tr key={cid} className="border-b border-border/40">
                  <td className="px-3 py-1.5 flex items-center gap-2">
                    <span className="w-2 h-2 rounded-full" style={{ background: CLUSTER_COLORS[i % CLUSTER_COLORS.length] }} />
                    {label || `Cluster ${cid}`}
                  </td>
                  <td className="px-3 py-1.5 text-right">{count}</td>
                  <td className="px-3 py-1.5 text-right text-muted-foreground">{pct}%</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Section: Search & Compose
// ---------------------------------------------------------------------------
function SearchSection({ indexId, skills }: { indexId: string; skills: Skill[] }) {
  const [query, setQuery] = useState('');
  const [task, setTask] = useState('');
  const [searchResults, setSearchResults] = useState<SearchResult[] | null>(null);
  const [playlist, setPlaylist] = useState<PlaylistItem[] | null>(null);
  const [searching, setSearching] = useState(false);
  const [composing, setComposing] = useState(false);

  const handleSearch = async () => {
    if (!query.trim()) return;
    setSearching(true); setPlaylist(null);
    try {
      const r = await fetch(`/api/bioskills-index/${indexId}/search?q=${encodeURIComponent(query)}&top_k=10`);
      const d = await r.json();
      setSearchResults(d.results || []);
    } finally { setSearching(false); }
  };

  const handleCompose = async () => {
    if (!task.trim()) return;
    setComposing(true); setSearchResults(null);
    try {
      const r = await fetch(`/api/bioskills-index/${indexId}/compose?task=${encodeURIComponent(task)}&max_skills=8`);
      const d = await r.json();
      setPlaylist(d.playlist || []);
    } finally { setComposing(false); }
  };

  const hasEmbeddings = skills.some(s => s.umap_x !== undefined);

  if (!hasEmbeddings) {
    return (
      <div className="text-center py-12 text-muted-foreground">
        <Search className="w-10 h-10 mx-auto mb-3 opacity-30" />
        <p className="mb-2">Embeddings required for search and compose.</p>
        <code className="text-xs font-mono bg-muted px-2 py-1 rounded">embed-and-project --index {indexId}</code>
      </div>
    );
  }

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
      <Card className="border-border">
        <CardHeader className="pb-2">
          <CardTitle className="text-base flex items-center gap-2">
            <Search className="w-4 h-4 text-emerald-400" /> Semantic Search
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-2">
          <div className="flex gap-2">
            <input
              value={query}
              onChange={e => setQuery(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && handleSearch()}
              placeholder="protein structure prediction..."
              className="flex-1 px-3 py-2 text-sm bg-muted border border-border rounded focus:outline-none focus:border-emerald-500/50"
            />
            <button onClick={handleSearch} disabled={searching}
              className="px-3 py-2 bg-emerald-600 hover:bg-emerald-500 text-white text-sm rounded disabled:opacity-50">
              {searching ? <Loader2 className="w-4 h-4 animate-spin" /> : 'Go'}
            </button>
          </div>
          {searchResults && (
            <div className="space-y-1 max-h-72 overflow-y-auto">
              {searchResults.map(r => (
                <div key={r.id} className="flex items-start justify-between p-2 rounded hover:bg-muted/50">
                  <div className="flex-1 min-w-0">
                    <Link href={`/bioskills-index/${indexId}/skill/${r.id}`} className={linkClass + ' text-sm truncate block'}>
                      {r.name}
                    </Link>
                    <span className="text-xs text-muted-foreground">{r.type}</span>
                  </div>
                  <span className="text-xs text-green-400 ml-2 shrink-0">{r.score.toFixed(2)}</span>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      <Card className="border-border">
        <CardHeader className="pb-2">
          <CardTitle className="text-base">Compose Workflow</CardTitle>
        </CardHeader>
        <CardContent className="space-y-2">
          <textarea
            value={task}
            onChange={e => setTask(e.target.value)}
            placeholder="analyze single-cell RNA from IPF lung samples..."
            rows={3}
            className="w-full px-3 py-2 text-sm bg-muted border border-border rounded focus:outline-none focus:border-emerald-500/50 resize-none"
          />
          <button onClick={handleCompose} disabled={composing}
            className="w-full py-2 bg-emerald-600 hover:bg-emerald-500 text-white text-sm rounded disabled:opacity-50 flex items-center justify-center gap-2">
            {composing ? <><Loader2 className="w-4 h-4 animate-spin" /> Composing...</> : 'Compose Playlist'}
          </button>
          {playlist && (
            <div className="space-y-1 max-h-72 overflow-y-auto mt-1">
              {playlist.map(item => (
                <div key={item.id} className="flex items-start gap-2 p-2 rounded hover:bg-muted/50">
                  <span className="text-xs text-muted-foreground w-4 shrink-0">{item.rank}.</span>
                  <div className="flex-1 min-w-0">
                    <Link href={`/bioskills-index/${indexId}/skill/${item.id}`} className={linkClass + ' text-sm truncate block'}>
                      {item.name}
                    </Link>
                    <span className="text-xs text-muted-foreground">{item.cluster_label || `Cluster ${item.cluster_id}`}</span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------
export default function IndexDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const [index, setIndex] = useState<BsiIndex | null>(null);
  const [skills, setSkills] = useState<Skill[]>([]);
  const [loading, setLoading] = useState(true);
  const [activeStage, setActiveStage] = useState<Stage>('setup');

  useEffect(() => {
    Promise.all([
      fetch(`/api/bioskills-index/${id}`).then(r => r.json()).then(d => setIndex(d.index ?? null)),
      fetch(`/api/bioskills-index/${id}/umap-data`).then(r => r.json()).then(d => setSkills(d.skills ?? [])),
    ]).finally(() => setLoading(false));
  }, [id]);

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <RefreshCw className="w-6 h-6 animate-spin text-muted-foreground" />
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-background text-foreground">
      {/* Header */}
      <div className="border-b border-border px-6 py-4">
        <div className="flex items-center gap-2 text-sm mb-1">
          <Link href="/" className={linkClass}>Hub</Link>
          <span className="text-muted-foreground">/</span>
          <Link href="/bioskills-index" className={linkClass}>Bioskills Index</Link>
          <span className="text-muted-foreground">/</span>
          <span className="text-muted-foreground font-mono">{index?.name ?? id.slice(0, 14)}</span>
        </div>
        <StageDots active={activeStage} />
      </div>

      {/* Body: sidebar + content */}
      <div className="flex">
        {/* Sidebar */}
        <nav className="w-44 shrink-0 border-r border-border min-h-screen sticky top-0 h-screen overflow-y-auto py-4">
          {STAGES.map(s => (
            <button
              key={s.key}
              onClick={() => setActiveStage(s.key)}
              className={`w-full flex items-center gap-2 px-4 py-2.5 text-sm transition-colors text-left ${
                activeStage === s.key
                  ? 'bg-emerald-500/10 text-emerald-400 border-r-2 border-emerald-400'
                  : 'text-muted-foreground hover:text-foreground hover:bg-muted/30'
              }`}
            >
              <span className={`w-5 h-5 rounded-full flex items-center justify-center text-xs font-bold shrink-0 ${
                activeStage === s.key ? 'bg-emerald-500/20 text-emerald-400' : 'bg-muted text-muted-foreground'
              }`}>
                {s.num}
              </span>
              <span className="truncate">{s.label}</span>
              {s.key === 'discovery' && skills.length > 0 && (
                <span className="ml-auto text-xs text-muted-foreground shrink-0">{skills.length}</span>
              )}
            </button>
          ))}
        </nav>

        {/* Content panel */}
        <main className="flex-1 p-6 overflow-y-auto">
          {activeStage === 'setup' && <SetupSection index={index} skillCount={skills.length} />}
          {activeStage === 'discovery' && <DiscoverySection skills={skills} indexId={id} />}
          {activeStage === 'annotation' && <AnnotationSection indexId={id} skills={skills} />}
          {activeStage === 'projection' && <ProjectionSection skills={skills} />}
          {activeStage === 'search' && <SearchSection indexId={id} skills={skills} />}
        </main>
      </div>
    </div>
  );
}
