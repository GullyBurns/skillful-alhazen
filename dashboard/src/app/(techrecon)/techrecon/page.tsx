'use client';

import { useState, useEffect, useCallback } from 'react';
import { Button } from '@/components/ui/button';
import { InvestigationCard } from '@/components/techrecon/investigation-card';
import { RefreshCw, ArrowLeft, Search } from 'lucide-react';
import Link from 'next/link';

interface InvestigationSummary {
  systems: number;
  artifacts: number;
  notes: number;
  components: number;
  concepts: number;
  data_models: number;
}

interface Investigation {
  id: string;
  name: string;
  description?: string;
  status: string;
  goal: string;
  created_at?: string;
  summary?: InvestigationSummary;
}

export default function TechReconDashboard() {
  const [investigations, setInvestigations] = useState<Investigation[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchData = useCallback(async () => {
    setLoading(true);
    setError(null);

    try {
      const res = await fetch('/api/techrecon/investigations');
      if (!res.ok) throw new Error('Failed to fetch investigations');
      const data = await res.json();
      setInvestigations(data.investigations || []);
    } catch (err) {
      console.error('Fetch error:', err);
      setError(err instanceof Error ? err.message : 'Failed to load data');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  return (
    <div className="min-h-screen">
      {/* Header */}
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
                <h1 className="text-2xl font-bold bg-gradient-to-r from-cyan-400 to-blue-400 bg-clip-text text-transparent">
                  TechRecon
                </h1>
                <p className="text-sm text-muted-foreground">
                  Systematic technology investigations
                </p>
              </div>
            </div>
            <Button
              variant="outline"
              size="sm"
              onClick={fetchData}
              disabled={loading}
              className="border-border/50 hover:border-primary/50 hover:bg-primary/10"
            >
              <RefreshCw className={`w-4 h-4 mr-2 ${loading ? 'animate-spin' : ''}`} />
              Refresh
            </Button>
          </div>
        </div>
      </header>

      <main className="container mx-auto px-4 py-6">
        {/* Error Alert */}
        {error && (
          <div className="bg-destructive/10 text-destructive px-4 py-3 rounded-lg mb-6">
            <strong>Error:</strong> {error}
            <p className="text-sm mt-1">
              Make sure TypeDB is running and the techrecon skill is configured.
            </p>
          </div>
        )}

        {/* Loading */}
        {loading && (
          <div className="flex items-center justify-center py-12">
            <RefreshCw className="w-6 h-6 animate-spin text-muted-foreground" />
          </div>
        )}

        {/* Investigation Cards Grid */}
        {!loading && investigations.length > 0 && (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {investigations.map((inv) => (
              <InvestigationCard key={inv.id} investigation={inv} />
            ))}
          </div>
        )}

        {/* Empty State */}
        {!loading && investigations.length === 0 && !error && (
          <div className="flex flex-col items-center justify-center py-16 text-center">
            <Search className="w-12 h-12 text-muted-foreground/50 mb-4" />
            <h2 className="text-lg font-medium mb-2">No investigations yet</h2>
            <p className="text-sm text-muted-foreground max-w-md">
              Start a TechRecon investigation using the CLI to explore software systems,
              then come back here to see your findings.
            </p>
          </div>
        )}
      </main>

      {/* Footer */}
      <footer className="border-t border-border/50 mt-8">
        <div className="container mx-auto px-4 py-4">
          <p className="text-xs text-muted-foreground text-center">
            TechRecon &bull; Powered by TypeDB + Next.js
          </p>
        </div>
      </footer>
    </div>
  );
}
