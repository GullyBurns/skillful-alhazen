'use client';

import { useState, useEffect, useCallback } from 'react';
import Link from 'next/link';
import { RefreshCw, ArrowLeft, Layers } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { DomainCard } from '@/components/skill-builder/domain-card';
import type { DomainSummary } from '@/components/skill-builder/domain-card';

interface DomainsResponse {
  success: boolean;
  count: number;
  domains: DomainSummary[];
}

export default function DomainModelingPage() {
  const [domains, setDomains] = useState<DomainSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch('/api/skill-builder/domains');
      if (!res.ok) throw new Error('Failed to fetch domains');
      const data: DomainsResponse = await res.json();
      setDomains(data.domains ?? []);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load data');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchData(); }, [fetchData]);

  return (
    <div className="min-h-screen">
      <header className="border-b border-border/50 bg-card/50 backdrop-blur-sm">
        <div className="container mx-auto px-4 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-6">
              <Link
                href="/"
                className="flex items-center gap-2 text-sm text-muted-foreground hover:text-primary transition-colors"
              >
                <ArrowLeft className="w-4 h-4" />
                Hub
              </Link>
              <div>
                <h1 className="text-2xl font-bold bg-gradient-to-r from-violet-400 to-purple-400 bg-clip-text text-transparent">
                  Domain Modeling
                </h1>
                <p className="text-sm text-muted-foreground">Skill design process tracking</p>
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

      <main className="container mx-auto px-4 py-6">
        {error && (
          <div className="bg-destructive/10 text-destructive px-4 py-3 rounded-lg mb-6">
            <strong>Error:</strong> {error}
            <p className="text-sm mt-1">Make sure TypeDB is running and the skill-builder skill is configured.</p>
          </div>
        )}

        {loading && (
          <div className="flex items-center justify-center py-12">
            <RefreshCw className="w-6 h-6 animate-spin text-muted-foreground" />
          </div>
        )}

        {!loading && domains.length > 0 && (
          <>
            <div className="mb-4 text-sm text-muted-foreground">
              {domains.length} domain{domains.length !== 1 ? 's' : ''} tracked
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {domains.map((domain) => (
                <DomainCard key={domain.id} domain={domain} />
              ))}
            </div>
          </>
        )}

        {!loading && domains.length === 0 && !error && (
          <div className="flex flex-col items-center justify-center py-16 text-center">
            <Layers className="w-12 h-12 text-muted-foreground/50 mb-4" />
            <h2 className="text-lg font-medium mb-2">No domains yet</h2>
            <p className="text-sm text-muted-foreground max-w-md">
              Create a domain tracking project with the CLI, then come back here to see your design process.
            </p>
            <pre className="mt-4 text-xs text-muted-foreground bg-muted/30 rounded px-4 py-3 text-left">
              uv run python .claude/skills/skill-builder/skill_builder.py \{'\n'}
              {'  '}init-domain --name &quot;My Skill&quot; --skill my-skill
            </pre>
          </div>
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
