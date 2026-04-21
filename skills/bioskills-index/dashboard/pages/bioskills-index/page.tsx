'use client';

import { useState, useEffect } from 'react';
import Link from 'next/link';
import { Network, Database, ChevronRight } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';

const linkClass =
  'text-cyan-400 font-semibold underline underline-offset-2 hover:text-blue-400 transition-colors';

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
  const [skillCounts, setSkillCounts] = useState<Record<string, number>>({});
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch('/api/bioskills-index')
      .then(r => r.json())
      .then(async (d) => {
        const idxList: BsiIndex[] = d.indices || [];
        setIndices(idxList);

        // Fetch real skill counts from umap-data (bsi-skill-count attr is stale)
        const counts: Record<string, number> = {};
        await Promise.all(
          idxList.map(idx =>
            fetch(`/api/bioskills-index/${idx.id}/umap-data`)
              .then(r => r.json())
              .then(data => { counts[idx.id] = (data.skills ?? []).length; })
              .catch(() => { counts[idx.id] = 0; })
          )
        );
        setSkillCounts(counts);
        setLoading(false);
      })
      .catch(() => setLoading(false));
  }, []);

  return (
    <div className="min-h-screen bg-background text-foreground p-8">
      <div className="max-w-4xl mx-auto">
        {/* Hub breadcrumb */}
        <div className="flex items-center gap-2 mb-6 text-sm">
          <Link href="/" className={linkClass}>Hub</Link>
          <span className="text-muted-foreground">/</span>
          <span className="text-muted-foreground">Bioskills Index</span>
        </div>

        <div className="flex items-center gap-3 mb-8">
          <Network className="w-8 h-8 text-emerald-400" />
          <div>
            <h1 className="text-3xl font-bold bg-gradient-to-r from-emerald-400 to-teal-400 bg-clip-text text-transparent">
              Bioskills Index
            </h1>
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
            <p className="mb-2">No indices found.</p>
            <code className="text-xs font-mono bg-muted px-2 py-1 rounded">
              uv run python bioskills_index.py create-index --name &quot;My Index&quot;
            </code>
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
                        <span>
                          <strong className="text-foreground">
                            {skillCounts[idx.id] ?? '…'}
                          </strong>{' '}
                          skills
                        </span>
                        {idx.created_at && (
                          <span>Created {new Date(idx.created_at).toLocaleDateString()}</span>
                        )}
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
