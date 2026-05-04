import type { PersonContext, MemoryClaimNote } from '@/lib/agentic-memory';
import { Brain, ArrowLeft, User, Tag, Link2, Wrench } from 'lucide-react';
import Link from 'next/link';

export const dynamic = 'force-dynamic';

const linkClass =
  'text-cyan-400 font-semibold underline underline-offset-2 hover:text-blue-400 transition-colors';

const BASE_URL = process.env.NEXT_PUBLIC_BASE_URL || 'http://localhost:3000';

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

function ContextSection({ label, value }: { label: string; value?: string }) {
  if (!value) return null;
  return (
    <div className="bg-card border border-border/50 rounded-lg p-4">
      <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-2">{label}</p>
      <p className="text-sm whitespace-pre-wrap">{value}</p>
    </div>
  );
}

interface PageProps {
  params: Promise<{ id: string }>;
}

export default async function PersonDetailPage({ params }: PageProps) {
  const { id } = await params;

  let ctx: PersonContext | null = null;
  let claims: MemoryClaimNote[] = [];
  let error: string | null = null;

  try {
    const [ctxRes, claimsRes] = await Promise.all([
      fetch(`${BASE_URL}/api/agentic-memory/context?person=${id}`, { cache: 'no-store' }),
      fetch(`${BASE_URL}/api/agentic-memory/facts?person=${id}&limit=100`, { cache: 'no-store' }),
    ]);

    if (ctxRes.ok) ctx = await ctxRes.json();
    else error = `Context API ${ctxRes.status}`;

    if (claimsRes.ok) {
      const json = await claimsRes.json();
      claims = Array.isArray(json) ? json : [];
    }
  } catch (err) {
    error = String(err);
  }

  const person = ctx?.context;
  const displayName = person?.['alh-given-name'] && person?.['alh-family-name']
    ? `${person['alh-given-name']} ${person['alh-family-name']}`
    : person?.name || id;

  // Group claims by alh-fact-type
  const claimsByType = claims.reduce<Record<string, MemoryClaimNote[]>>((acc, c) => {
    const t = c['alh-fact-type'] || 'unknown';
    if (!acc[t]) acc[t] = [];
    acc[t].push(c);
    return acc;
  }, {});

  return (
    <div className="min-h-screen">
      {/* Header */}
      <header className="border-b border-border/50 bg-card/50 backdrop-blur-sm">
        <div className="container mx-auto px-4 py-4">
          <div className="flex items-center gap-6">
            <Link href="/agentic-memory" className={`flex items-center gap-2 text-sm ${linkClass}`}>
              <ArrowLeft className="w-4 h-4" />
              Agentic Memory
            </Link>
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-full bg-indigo-900/50 border border-indigo-700 flex items-center justify-center">
                <User className="w-5 h-5 text-indigo-300" />
              </div>
              <div>
                <h1 className="text-xl font-bold">{displayName}</h1>
                <p className="text-xs font-mono text-muted-foreground">{id}</p>
              </div>
            </div>
          </div>
        </div>
      </header>

      <main className="container mx-auto px-4 py-6 space-y-8">
        {error && (
          <div className="bg-destructive/10 text-destructive px-4 py-3 rounded-lg">
            <strong>Error:</strong> {error}
          </div>
        )}

        {/* Personal Context Domains */}
        {person && (
          <section>
            <h2 className="text-lg font-semibold mb-4 flex items-center gap-2">
              <User className="w-5 h-5 text-indigo-400" />
              Personal Context
            </h2>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <ContextSection label="Identity" value={person['nbmem-identity-summary']} />
              <ContextSection label="Role" value={person['nbmem-role-description']} />
              <ContextSection label="Communication Style" value={person['nbmem-communication-style']} />
              <ContextSection label="Goals" value={person['nbmem-goals-summary']} />
              <ContextSection label="Preferences" value={person['nbmem-preferences-summary']} />
              <ContextSection label="Domain Expertise" value={person['nbmem-domain-expertise']} />
            </div>
          </section>
        )}

        {/* Linked Projects */}
        {ctx?.projects && ctx.projects.length > 0 && (
          <section>
            <h2 className="text-lg font-semibold mb-4 flex items-center gap-2">
              <Link2 className="w-5 h-5 text-cyan-400" />
              Projects
            </h2>
            <div className="flex flex-wrap gap-2">
              {ctx.projects.map((p) => (
                <span
                  key={p.id}
                  className="bg-cyan-900/30 text-cyan-300 border border-cyan-800 px-3 py-1 rounded text-sm"
                >
                  {p.name}
                </span>
              ))}
            </div>
          </section>
        )}

        {/* Linked Tools */}
        {ctx?.tools && ctx.tools.length > 0 && (
          <section>
            <h2 className="text-lg font-semibold mb-4 flex items-center gap-2">
              <Wrench className="w-5 h-5 text-amber-400" />
              Tools & Systems
            </h2>
            <div className="flex flex-wrap gap-2">
              {ctx.tools.map((t) => (
                <span
                  key={t.id}
                  className="bg-amber-900/30 text-amber-300 border border-amber-800 px-3 py-1 rounded text-sm"
                >
                  {t.name}
                </span>
              ))}
            </div>
          </section>
        )}

        {/* Memory Claims by Type */}
        {claims.length > 0 && (
          <section>
            <h2 className="text-lg font-semibold mb-4 flex items-center gap-2">
              <Brain className="w-5 h-5 text-teal-400" />
              Memory Claims
              <span className="text-xs text-muted-foreground bg-muted px-2 py-0.5 rounded-full">
                {claims.length}
              </span>
            </h2>
            <div className="space-y-6">
              {Object.entries(claimsByType).map(([type, typeClaims]) => (
                <div key={type}>
                  <div className="flex items-center gap-2 mb-3">
                    <FactTypeBadge type={type} />
                    <span className="text-xs text-muted-foreground">{typeClaims.length}</span>
                  </div>
                  <div className="space-y-2 ml-2">
                    {typeClaims.map((c) => (
                      <div
                        key={c.id}
                        className="bg-card border border-border/50 rounded px-3 py-2 flex items-start gap-3"
                      >
                        <p className="text-sm flex-1">{c.content}</p>
                        <div className="shrink-0 text-right">
                          {c.confidence != null && (
                            <span className="text-xs text-muted-foreground block">
                              {Math.round(c.confidence * 100)}%
                            </span>
                          )}
                          {c['valid-until'] && (
                            <span className="text-xs text-amber-500 block">
                              expires {new Date(c['valid-until']).toLocaleDateString()}
                            </span>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          </section>
        )}

        {claims.length === 0 && !error && (
          <p className="text-sm text-muted-foreground italic">
            No memory claims for this person yet. Use{' '}
            <code className="text-xs bg-muted px-1 rounded">consolidate --subject {id}</code>
          </p>
        )}
      </main>
    </div>
  );
}
