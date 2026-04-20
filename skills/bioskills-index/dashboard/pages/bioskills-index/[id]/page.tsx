'use client';

import { useState, useEffect, useRef, use } from 'react';
import Link from 'next/link';
import * as Plot from '@observablehq/plot';
import { Search, Network, Loader2, ExternalLink } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';

type Skill = {
  id: string;
  name: string;
  bsi_type: string;
  cluster_id: number;
  cluster_label: string;
  umap_x: number;
  umap_y: number;
  source_repo: string;
};

type SearchResult = {
  id: string;
  name: string;
  score: number;
  type: string;
  source_repo: string;
};

type PlaylistItem = {
  rank: number;
  id: string;
  name: string;
  score: number;
  cluster_id: number;
  cluster_label: string;
  type: string;
};

const CLUSTER_COLORS = ['#34d399', '#60a5fa', '#f472b6', '#fb923c', '#a78bfa', '#facc15'];

export default function IndexDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const plotRef = useRef<HTMLDivElement>(null);
  const [skills, setSkills] = useState<Skill[]>([]);
  const [query, setQuery] = useState('');
  const [task, setTask] = useState('');
  const [searchResults, setSearchResults] = useState<SearchResult[] | null>(null);
  const [playlist, setPlaylist] = useState<PlaylistItem[] | null>(null);
  const [searching, setSearching] = useState(false);
  const [composing, setComposing] = useState(false);
  const [selectedCluster, setSelectedCluster] = useState<number | null>(null);
  const [highlightedId, setHighlightedId] = useState<string | null>(null);

  useEffect(() => {
    fetch(`/api/bioskills-index/${id}/umap-data`)
      .then(r => r.json())
      .then(d => setSkills(d.skills || []));
  }, [id]);

  // Build UMAP scatter with Observable Plot
  useEffect(() => {
    if (!plotRef.current || skills.length === 0) return;
    const filtered = selectedCluster !== null
      ? skills.filter(s => s.cluster_id === selectedCluster)
      : skills;

    const clusterIds = [...new Set(skills.map(s => s.cluster_id))].sort();
    const colorScale = Object.fromEntries(clusterIds.map((cid, i) => [cid, CLUSTER_COLORS[i % CLUSTER_COLORS.length]]));

    const plot = Plot.plot({
      width: plotRef.current.clientWidth || 600,
      height: 380,
      style: { background: 'transparent', color: '#e2e8f0' },
      x: { label: null, ticks: [] },
      y: { label: null, ticks: [] },
      marks: [
        Plot.dot(filtered, {
          x: 'umap_x',
          y: 'umap_y',
          r: 4,
          fill: (d: Skill) => colorScale[d.cluster_id] ?? '#6b7280',
          fillOpacity: (d: Skill) => highlightedId && d.id !== highlightedId ? 0.2 : 0.85,
          title: (d: Skill) => `${d.name}\n${d.cluster_label || `Cluster ${d.cluster_id}`}`,
          tip: true,
        }),
      ],
    });

    plotRef.current.innerHTML = '';
    plotRef.current.appendChild(plot);
    return () => plot.remove();
  }, [skills, selectedCluster, highlightedId]);

  const handleSearch = async () => {
    if (!query.trim()) return;
    setSearching(true);
    setPlaylist(null);
    try {
      const r = await fetch(`/api/bioskills-index/${id}/search?q=${encodeURIComponent(query)}&top_k=10`);
      const d = await r.json();
      setSearchResults(d.results || []);
    } finally {
      setSearching(false);
    }
  };

  const handleCompose = async () => {
    if (!task.trim()) return;
    setComposing(true);
    setSearchResults(null);
    try {
      const r = await fetch(`/api/bioskills-index/${id}/compose?task=${encodeURIComponent(task)}&max_skills=8`);
      const d = await r.json();
      setPlaylist(d.playlist || []);
    } finally {
      setComposing(false);
    }
  };

  const clusters = [...new Map(skills.map(s => [s.cluster_id, s.cluster_label])).entries()]
    .filter(([cid]) => cid !== -1)
    .sort(([a], [b]) => a - b);

  return (
    <div className="min-h-screen bg-background text-foreground p-6">
      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <div className="flex items-center gap-2 mb-6">
          <Link href="/bioskills-index" className="text-emerald-400 hover:text-emerald-300 text-sm">
            Bioskills Index
          </Link>
          <span className="text-muted-foreground">/</span>
          <span className="text-sm font-mono text-muted-foreground">{id}</span>
        </div>
        <div className="flex items-center gap-3 mb-6">
          <Network className="w-6 h-6 text-emerald-400" />
          <h1 className="text-2xl font-bold">{skills.length} skills indexed</h1>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* UMAP Scatter */}
          <div className="lg:col-span-2">
            <Card className="border-border">
              <CardHeader className="pb-2">
                <div className="flex items-center justify-between">
                  <CardTitle className="text-base">Skill Landscape</CardTitle>
                  <button
                    onClick={() => setSelectedCluster(null)}
                    className="text-xs text-muted-foreground hover:text-foreground"
                  >
                    {selectedCluster !== null ? 'Clear filter' : ''}
                  </button>
                </div>
                <div className="flex flex-wrap gap-2 mt-2">
                  {clusters.map(([cid, label], i) => (
                    <button
                      key={cid}
                      onClick={() => setSelectedCluster(selectedCluster === cid ? null : cid)}
                      className={`flex items-center gap-1.5 px-2 py-1 rounded text-xs transition-all ${
                        selectedCluster === cid ? 'ring-1 ring-white/30' : 'opacity-70 hover:opacity-100'
                      }`}
                      style={{ background: `${CLUSTER_COLORS[i]}22`, color: CLUSTER_COLORS[i] }}
                    >
                      <span className="w-2 h-2 rounded-full" style={{ background: CLUSTER_COLORS[i] }} />
                      {label || `Cluster ${cid}`}
                    </button>
                  ))}
                </div>
              </CardHeader>
              <CardContent>
                <div ref={plotRef} className="w-full" />
                {skills.length === 0 && (
                  <div className="h-64 flex items-center justify-center text-muted-foreground">
                    <p>No UMAP data. Run <code className="font-mono text-sm">embed-and-project</code> first.</p>
                  </div>
                )}
              </CardContent>
            </Card>
          </div>

          {/* Search + Compose Panel */}
          <div className="flex flex-col gap-4">
            <Card className="border-border">
              <CardHeader className="pb-2">
                <CardTitle className="text-base flex items-center gap-2">
                  <Search className="w-4 h-4 text-emerald-400" />
                  Semantic Search
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
                  <button
                    onClick={handleSearch}
                    disabled={searching}
                    className="px-3 py-2 bg-emerald-600 hover:bg-emerald-500 text-white text-sm rounded disabled:opacity-50"
                  >
                    {searching ? <Loader2 className="w-4 h-4 animate-spin" /> : 'Go'}
                  </button>
                </div>
                {searchResults && (
                  <div className="space-y-1 max-h-64 overflow-y-auto">
                    {searchResults.map(r => (
                      <div
                        key={r.id}
                        className="flex items-start justify-between p-2 rounded hover:bg-muted/50 cursor-pointer"
                        onMouseEnter={() => setHighlightedId(r.id)}
                        onMouseLeave={() => setHighlightedId(null)}
                      >
                        <div className="flex-1 min-w-0">
                          <Link href={`/bioskills-index/${id}/skill/${r.id}`}
                            className="text-sm text-emerald-400 font-medium hover:underline truncate block">
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
                <button
                  onClick={handleCompose}
                  disabled={composing}
                  className="w-full py-2 bg-emerald-600 hover:bg-emerald-500 text-white text-sm rounded disabled:opacity-50 flex items-center justify-center gap-2"
                >
                  {composing ? <><Loader2 className="w-4 h-4 animate-spin" /> Composing...</> : 'Compose Playlist'}
                </button>
                {playlist && (
                  <div className="space-y-1 max-h-72 overflow-y-auto mt-1">
                    {playlist.map(item => (
                      <div key={item.id} className="flex items-start gap-2 p-2 rounded hover:bg-muted/50">
                        <span className="text-xs text-muted-foreground w-4 shrink-0">{item.rank}.</span>
                        <div className="flex-1 min-w-0">
                          <Link href={`/bioskills-index/${id}/skill/${item.id}`}
                            className="text-sm text-emerald-400 hover:underline truncate block">
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

            <Card className="border-border">
              <CardHeader className="pb-2">
                <CardTitle className="text-base">Browse by EDAM</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-1">
                  {[
                    ['operation_2403', 'Sequence analysis'],
                    ['operation_2495', 'Expression analysis'],
                    ['operation_3197', 'Genetic variation analysis'],
                    ['operation_0477', 'Protein modelling'],
                    ['operation_3760', 'Service management'],
                    ['operation_3200', 'Community profiling'],
                  ].map(([edam_id, label]) => (
                    <Link
                      key={edam_id}
                      href={`/bioskills-index/${id}/edam/${edam_id}`}
                      className="flex items-center justify-between px-2 py-1.5 rounded hover:bg-muted/50 text-sm group"
                    >
                      <span className="text-emerald-400 group-hover:text-emerald-300">{label}</span>
                      <span className="text-xs font-mono text-muted-foreground">{edam_id}</span>
                    </Link>
                  ))}
                  <div className="pt-2 border-t border-border mt-2">
                    <Link
                      href={`/bioskills-index/${id}/edam/operation_0004`}
                      className="text-xs text-muted-foreground hover:text-foreground flex items-center gap-1"
                    >
                      Browse full EDAM tree <ExternalLink className="w-3 h-3" />
                    </Link>
                  </div>
                </div>
              </CardContent>
            </Card>
          </div>
        </div>
      </div>
    </div>
  );
}
