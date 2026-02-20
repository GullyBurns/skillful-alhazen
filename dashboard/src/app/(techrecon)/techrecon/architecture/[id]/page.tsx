'use client';

import { useState, useEffect, use } from 'react';
import Link from 'next/link';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { ArrowLeft, RefreshCw, Server } from 'lucide-react';
import { ArchitectureMap } from '@/components/techrecon/architecture-map';

interface ArchitecturePageProps {
  params: Promise<{ id: string }>;
}

export default function ArchitecturePage({ params }: ArchitecturePageProps) {
  const { id } = use(params);
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function fetchArchitecture() {
      setLoading(true);
      setError(null);
      try {
        const res = await fetch(`/api/techrecon/architecture/${id}`);
        if (!res.ok) throw new Error('Failed to fetch architecture');
        const json = await res.json();
        setData(json);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Unknown error');
      } finally {
        setLoading(false);
      }
    }
    fetchArchitecture();
  }, [id]);

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <RefreshCw className="w-8 h-8 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="min-h-screen p-8">
        <Link href="/techrecon">
          <Button variant="ghost" className="mb-4">
            <ArrowLeft className="w-4 h-4 mr-2" />
            Back to TechRecon
          </Button>
        </Link>
        <div className="bg-destructive/10 text-destructive px-4 py-3 rounded-lg">
          <strong>Error:</strong> {error || 'Architecture not found'}
        </div>
      </div>
    );
  }

  const system = data.system || {};
  const components = data.components || [];
  const conceptLinks = data.concept_links || [];
  const componentDependencies = data.component_dependencies || [];

  return (
    <div className="min-h-screen">
      {/* Header */}
      <header className="border-b border-border/50 bg-card/50 backdrop-blur-sm">
        <div className="container mx-auto px-4 py-4">
          <Link href={`/techrecon/system/${id}`}>
            <Button variant="ghost" size="sm" className="mb-2 hover:bg-primary/10">
              <ArrowLeft className="w-4 h-4 mr-2" />
              Back to {system.name || 'System'}
            </Button>
          </Link>
          <div className="flex items-start justify-between">
            <div>
              <h1 className="text-2xl font-bold bg-gradient-to-r from-cyan-400 to-blue-400 bg-clip-text text-transparent flex items-center gap-3">
                <Server className="w-6 h-6 text-cyan-400" />
                {system.name || 'Unknown'} Architecture
              </h1>
              <p className="text-sm text-muted-foreground mt-1">
                Component and concept map
              </p>
            </div>
            <Badge variant="secondary">{components.length} components</Badge>
          </div>
        </div>
      </header>

      <main className="container mx-auto px-4 py-6">
        <ArchitectureMap
          components={components}
          conceptLinks={conceptLinks}
          componentDependencies={componentDependencies}
        />
      </main>
    </div>
  );
}
