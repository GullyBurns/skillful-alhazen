'use client';

import { useState, useEffect, use } from 'react';
import Link from 'next/link';
import { Network, ChevronRight } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';

type EDAMOperation = {
  id: string;
  edam_id: string;
  name: string;
  definition: string;
  edam_source: string;
  implementing_skill_count: number;
};

type SkillItem = {
  id: string;
  name: string;
  bsi_type: string;
  cluster_label: string;
  source_repo: string;
};

export default function EDAMTermPage({
  params,
}: {
  params: Promise<{ id: string; eid: string }>;
}) {
  const { id, eid } = use(params);
  const [operation, setOperation] = useState<EDAMOperation | null>(null);
  const [skills, setSkills] = useState<SkillItem[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // Fetch EDAM operation details
    fetch(`/api/bioskills-index/edam/${eid}`)
      .then(r => r.json())
      .then(d => setOperation(d.operation || null))
      .catch(() => {});

    // Fetch skills implementing this operation (via BFS)
    fetch(`/api/bioskills-index/${id}/skills-by-edam?op=${eid}`)
      .then(r => r.json())
      .then(d => { setSkills(d.skills || []); setLoading(false); })
      .catch(() => setLoading(false));
  }, [id, eid]);

  return (
    <div className="min-h-screen bg-background text-foreground p-6">
      <div className="max-w-4xl mx-auto">
        {/* Breadcrumb */}
        <div className="flex items-center gap-2 mb-6 text-sm">
          <Link href="/bioskills-index" className="text-emerald-400 hover:text-emerald-300">Bioskills Index</Link>
          <span className="text-muted-foreground">/</span>
          <Link href={`/bioskills-index/${id}`} className="text-emerald-400 hover:text-emerald-300 font-mono">{id.slice(0, 12)}...</Link>
          <span className="text-muted-foreground">/</span>
          <span className="text-muted-foreground">edam</span>
          <span className="text-muted-foreground">/</span>
          <span className="font-mono text-muted-foreground">{eid}</span>
        </div>

        {operation ? (
          <>
            <div className="flex items-start gap-3 mb-4">
              <Network className="w-6 h-6 text-emerald-400 mt-1 shrink-0" />
              <div>
                <h1 className="text-2xl font-bold">{operation.name}</h1>
                <div className="flex items-center gap-2 mt-1">
                  <code className="text-xs font-mono text-muted-foreground">{operation.edam_id}</code>
                  <Badge variant="outline" className="text-xs">{operation.edam_source}</Badge>
                </div>
              </div>
            </div>

            {operation.definition && (
              <p className="text-muted-foreground mb-6 leading-relaxed">{operation.definition}</p>
            )}
          </>
        ) : (
          <div className="mb-6">
            <h1 className="text-2xl font-bold font-mono">{eid}</h1>
          </div>
        )}

        <Card className="border-border">
          <CardHeader className="pb-2">
            <CardTitle className="text-base">
              Implementing Skills
              <span className="text-muted-foreground font-normal ml-2 text-sm">
                ({loading ? '...' : skills.length} skills via transitive EDAM hierarchy)
              </span>
            </CardTitle>
          </CardHeader>
          <CardContent>
            {loading ? (
              <p className="text-muted-foreground text-sm">Loading...</p>
            ) : skills.length === 0 ? (
              <p className="text-muted-foreground text-sm">No skills implement this operation.</p>
            ) : (
              <div className="space-y-1">
                {skills.map(s => (
                  <Link
                    key={s.id}
                    href={`/bioskills-index/${id}/skill/${s.id}`}
                    className="flex items-center justify-between px-3 py-2 rounded hover:bg-muted/50 group"
                  >
                    <div className="flex items-center gap-2 min-w-0">
                      <span className="text-sm text-emerald-400 group-hover:text-emerald-300 truncate">
                        {s.name}
                      </span>
                      {s.bsi_type && (
                        <Badge variant="outline" className="text-xs shrink-0">{s.bsi_type}</Badge>
                      )}
                    </div>
                    <div className="flex items-center gap-2 shrink-0">
                      {s.cluster_label && (
                        <span className="text-xs text-muted-foreground">{s.cluster_label}</span>
                      )}
                      <ChevronRight className="w-4 h-4 text-muted-foreground opacity-0 group-hover:opacity-100" />
                    </div>
                  </Link>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
