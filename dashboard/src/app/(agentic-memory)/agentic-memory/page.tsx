import type { Person, MemoryClaimNote, Episode } from '@/lib/agentic-memory';
import { Brain, ArrowLeft, User, Clock, Tag, Network } from 'lucide-react';
import Link from 'next/link';

export const dynamic = 'force-dynamic';

const linkClass =
  'text-cyan-400 font-semibold underline underline-offset-2 hover:text-blue-400 transition-colors';

const BASE_URL = process.env.NEXT_PUBLIC_BASE_URL || 'http://localhost:3000';

async function fetchJson<T>(path: string): Promise<{ data: T | null; error: string | null }> {
  try {
    const res = await fetch(`${BASE_URL}${path}`, { cache: 'no-store' });
    if (!res.ok) return { data: null, error: `API ${res.status}` };
    return { data: await res.json() as T, error: null };
  } catch (err) {
    return { data: null, error: String(err) };
  }
}

function FactTypeBadge({ type }: { type?: string }) {
  const colors: Record<string, string> = {
    knowledge: 'bg-teal-900/50 text-teal-300 border-teal-700',
    decision: 'bg-indigo-900/50 text-indigo-300 border-indigo-700',
    goal: 'bg-amber-900/50 text-amber-300 border-amber-700',
    preference: 'bg-purple-900/50 text-purple-300 border-purple-700',
    'slog-schema-gap': 'bg-red-900/50 text-red-300 border-red-700',
  };
  const cls = colors[type || ''] || 'bg-slate-800 text-slate-400 border-slate-700';
  return (
    <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs border ${cls}`}>
      <Tag className="w-3 h-3" />
      {type || 'unknown'}
    </span>
  );
}

export default async function AgenticMemoryPage() {
  const [personsResult, claimsResult, episodesResult] = await Promise.all([
    fetchJson<Person[]>('/api/agentic-memory/persons'),
    fetchJson<MemoryClaimNote[]>('/api/agentic-memory/facts?limit=20'),
    fetchJson<Episode[]>('/api/agentic-memory/episodes?limit=10'),
  ]);

  const persons = personsResult.data || [];
  const claims = claimsResult.data || [];
  const episodes = episodesResult.data || [];
  const error = personsResult.error || claimsResult.error || episodesResult.error;

  return (
    <div className="min-h-screen">
      {/* Header */}
      <header className="border-b border-border/50 bg-card/50 backdrop-blur-sm">
        <div className="container mx-auto px-4 py-4">
          <div className="flex items-center gap-6">
            <Link href="/" className={`flex items-center gap-2 text-sm ${linkClass}`}>
              <ArrowLeft className="w-4 h-4" />
              Hub
            </Link>
            <div>
              <h1 className="text-2xl font-bold bg-gradient-to-r from-teal-400 to-indigo-400 bg-clip-text text-transparent">
                Agentic Memory
              </h1>
              <p className="text-sm text-muted-foreground">
                TypeDB-backed two-tier ontological memory
              </p>
            </div>
          </div>
        </div>
      </header>

      <main className="container mx-auto px-4 py-6 space-y-8">
        {/* Knowledge Graph Browser link */}
        <Link
          href="/agentic-memory/graph-browser"
          className="block bg-card border border-border/50 rounded-lg p-5 hover:border-cyan-500/50 transition-colors group"
        >
          <div className="flex items-center gap-4">
            <div className="w-12 h-12 rounded-lg bg-cyan-900/30 border border-cyan-700/50 flex items-center justify-center group-hover:border-cyan-500/50 transition-colors">
              <Network className="w-6 h-6 text-cyan-400" />
            </div>
            <div>
              <h2 className="text-lg font-semibold bg-gradient-to-r from-cyan-400 to-blue-500 bg-clip-text text-transparent">
                Knowledge Graph Browser
              </h2>
              <p className="text-sm text-muted-foreground mt-0.5">
                Browse entity types, search instances, and visualize graph neighborhoods
              </p>
            </div>
          </div>
        </Link>

        {error && (
          <div className="bg-destructive/10 text-destructive px-4 py-3 rounded-lg">
            <strong>Error:</strong> {error}
            <p className="text-sm mt-1">Make sure TypeDB is running and agentic-memory schema is loaded.</p>
          </div>
        )}

        {/* Persons */}
        <section>
          <div className="flex items-center gap-2 mb-4">
            <User className="w-5 h-5 text-indigo-400" />
            <h2 className="text-lg font-semibold">Persons</h2>
            <span className="text-xs text-muted-foreground bg-muted px-2 py-0.5 rounded-full">
              {persons.length}
            </span>
          </div>
          {persons.length === 0 ? (
            <p className="text-sm text-muted-foreground italic">
              No persons yet. Create one with{' '}
              <code className="text-xs bg-muted px-1 rounded">agentic_memory.py create-operator</code>
            </p>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {persons.map((p) => (
                <Link
                  key={p.id}
                  href={`/agentic-memory/person/${p.id}`}
                  className="block bg-card border border-border/50 rounded-lg p-4 hover:border-indigo-500/50 transition-colors"
                >
                  <div className="flex items-center gap-3 mb-2">
                    <div className="w-8 h-8 rounded-full bg-indigo-900/50 border border-indigo-700 flex items-center justify-center">
                      <User className="w-4 h-4 text-indigo-300" />
                    </div>
                    <div>
                      <p className="font-medium text-sm">
                        {p['alh-given-name'] && p['alh-family-name']
                          ? `${p['alh-given-name']} ${p['alh-family-name']}`
                          : p.name || p.id}
                      </p>
                      <p className="text-xs text-muted-foreground font-mono">{p.id}</p>
                    </div>
                  </div>
                  {p['nbmem-role-description'] && (
                    <p className="text-xs text-muted-foreground line-clamp-2 mt-2">
                      {p['nbmem-role-description']}
                    </p>
                  )}
                </Link>
              ))}
            </div>
          )}
        </section>

        {/* Recent Memory-Claim-Notes */}
        <section>
          <div className="flex items-center gap-2 mb-4">
            <Brain className="w-5 h-5 text-teal-400" />
            <h2 className="text-lg font-semibold">Recent Memory Claims</h2>
            <span className="text-xs text-muted-foreground bg-muted px-2 py-0.5 rounded-full">
              {claims.length}
            </span>
          </div>
          {claims.length === 0 ? (
            <p className="text-sm text-muted-foreground italic">
              No memory claims yet. Use <code className="text-xs bg-muted px-1 rounded">consolidate</code> to crystallize knowledge.
            </p>
          ) : (
            <div className="space-y-2">
              {claims.map((c) => (
                <div
                  key={c.id}
                  className="bg-card border border-border/50 rounded-lg px-4 py-3 flex items-start gap-3"
                >
                  <FactTypeBadge type={c['alh-fact-type']} />
                  <p className="text-sm flex-1">{c.content}</p>
                  {c.confidence != null && (
                    <span className="text-xs text-muted-foreground shrink-0">
                      {Math.round(c.confidence * 100)}%
                    </span>
                  )}
                </div>
              ))}
            </div>
          )}
        </section>

        {/* Recent Episodes */}
        <section>
          <div className="flex items-center gap-2 mb-4">
            <Clock className="w-5 h-5 text-amber-400" />
            <h2 className="text-lg font-semibold">Recent Episodes</h2>
            <span className="text-xs text-muted-foreground bg-muted px-2 py-0.5 rounded-full">
              {episodes.length}
            </span>
          </div>
          {episodes.length === 0 ? (
            <p className="text-sm text-muted-foreground italic">
              No episodes yet. Create one with <code className="text-xs bg-muted px-1 rounded">create-episode</code> at session close.
            </p>
          ) : (
            <div className="space-y-2">
              {episodes.map((ep) => (
                <div
                  key={ep.id}
                  className="bg-card border border-border/50 rounded-lg px-4 py-3"
                >
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-xs font-mono text-muted-foreground">{ep.id}</span>
                    <div className="flex items-center gap-2">
                      {ep['alh-source-skill'] && (
                        <span className="text-xs bg-amber-900/30 text-amber-300 border border-amber-800 px-2 py-0.5 rounded">
                          {ep['alh-source-skill']}
                        </span>
                      )}
                      {ep['created-at'] && (
                        <span className="text-xs text-muted-foreground">
                          {new Date(ep['created-at']).toLocaleDateString()}
                        </span>
                      )}
                    </div>
                  </div>
                  <p className="text-sm line-clamp-2">{ep.content}</p>
                </div>
              ))}
            </div>
          )}
        </section>
      </main>
    </div>
  );
}
