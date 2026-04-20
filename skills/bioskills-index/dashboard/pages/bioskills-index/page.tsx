'use client';

import { useState, useEffect } from 'react';
import Link from 'next/link';
import { Network, Database, ChevronRight } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';

type BsiIndex = {
  id: string;
  name: string;
  version: number;
  skill_count: number;
  status: string;
  created_at: string;
};

export default function BioskillsIndexPage() {
  const [indices, setIndices] = useState<BsiIndex[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch('/api/bioskills-index')
      .then(r => r.json())
      .then(d => { setIndices(d.indices || []); setLoading(false); })
      .catch(() => setLoading(false));
  }, []);

  return (
    <div className="min-h-screen bg-background text-foreground p-8">
      <div className="max-w-4xl mx-auto">
        <div className="flex items-center gap-3 mb-8">
          <Network className="w-8 h-8 text-emerald-400" />
          <div>
            <h1 className="text-3xl font-bold">Bioskills Index</h1>
            <p className="text-muted-foreground mt-1">
              EDAM-annotated index of bioskills available online
            </p>
          </div>
        </div>

        {loading ? (
          <p className="text-muted-foreground">Loading indices...</p>
        ) : indices.length === 0 ? (
          <div className="text-center py-16 text-muted-foreground">
            <Database className="w-12 h-12 mx-auto mb-4 opacity-40" />
            <p>No indices found. Run <code className="font-mono text-sm">create-index</code> to get started.</p>
          </div>
        ) : (
          <div className="grid gap-4">
            {indices.map(idx => (
              <Link key={idx.id} href={`/bioskills-index/${idx.id}`}>
                <Card className="border-border hover:border-emerald-500/50 transition-colors cursor-pointer">
                  <CardHeader className="pb-2">
                    <div className="flex items-start justify-between">
                      <CardTitle className="text-lg text-emerald-400">{idx.name}</CardTitle>
                      <div className="flex items-center gap-2">
                        <Badge variant="outline" className="text-xs">v{idx.version}</Badge>
                        <Badge
                          variant="outline"
                          className={`text-xs ${idx.status === 'active' ? 'text-green-400 border-green-500/30' : 'text-yellow-400 border-yellow-500/30'}`}
                        >
                          {idx.status}
                        </Badge>
                      </div>
                    </div>
                  </CardHeader>
                  <CardContent>
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-4 text-sm text-muted-foreground">
                        <span><strong className="text-foreground">{idx.skill_count ?? '–'}</strong> skills</span>
                        <span>Created {new Date(idx.created_at).toLocaleDateString()}</span>
                      </div>
                      <ChevronRight className="w-4 h-4 text-muted-foreground" />
                    </div>
                  </CardContent>
                </Card>
              </Link>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
