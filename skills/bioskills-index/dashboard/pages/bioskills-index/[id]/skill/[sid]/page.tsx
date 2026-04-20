'use client';

import { useState, useEffect, use } from 'react';
import Link from 'next/link';
import { ExternalLink, Tag, Code } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';

type SkillDetail = {
  id: string;
  name: string;
  description: string;
  type: string;
  source_repo: string;
  cluster_label: string;
  cluster_id: number;
};

type ShowSkillResponse = {
  success: boolean;
  skill: SkillDetail;
  operations: Array<{ op_edam_id: string; op_name: string; op_source: string }>;
  topics: Array<{ topic_edam_id: string; topic_name: string }>;
  snippets: Array<{ id: string; name: string; content: string; snippet_type: string; language: string }>;
};

export default function SkillDetailPage({
  params,
}: {
  params: Promise<{ id: string; sid: string }>;
}) {
  const { id, sid } = use(params);
  const [data, setData] = useState<ShowSkillResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [expandedSnippet, setExpandedSnippet] = useState<string | null>(null);

  useEffect(() => {
    fetch(`/api/bioskills-index/skill/${sid}`)
      .then(r => r.json())
      .then(d => { setData(d); setLoading(false); })
      .catch(() => setLoading(false));
  }, [sid]);

  const skill = data?.skill ?? null;

  if (loading) return <div className="p-8 text-muted-foreground">Loading...</div>;
  if (!skill) return <div className="p-8 text-muted-foreground">Skill not found.</div>;

  return (
    <div className="min-h-screen bg-background text-foreground p-6">
      <div className="max-w-4xl mx-auto">
        {/* Breadcrumb */}
        <div className="flex items-center gap-2 mb-6 text-sm">
          <Link href="/bioskills-index" className="text-emerald-400 hover:text-emerald-300">Bioskills Index</Link>
          <span className="text-muted-foreground">/</span>
          <Link href={`/bioskills-index/${id}`} className="text-emerald-400 hover:text-emerald-300 font-mono">{id.slice(0, 12)}...</Link>
          <span className="text-muted-foreground">/</span>
          <span className="text-muted-foreground">skill</span>
        </div>

        <h1 className="text-2xl font-bold mb-1">{skill.name}</h1>
        <div className="flex items-center gap-2 mb-4">
          <Badge variant="outline" className="text-xs">{skill.type}</Badge>
          {skill.cluster_label && (
            <Badge variant="outline" className="text-xs text-emerald-400 border-emerald-500/30">
              {skill.cluster_label}
            </Badge>
          )}
          {skill.source_repo && (
            <a href={skill.source_repo} target="_blank" rel="noopener noreferrer"
              className="text-xs text-blue-400 flex items-center gap-1 hover:underline">
              <ExternalLink className="w-3 h-3" /> source
            </a>
          )}
        </div>

        {skill.description && (
          <p className="text-muted-foreground mb-6">{skill.description}</p>
        )}

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
          {/* EDAM Operations */}
          <Card className="border-border">
            <CardHeader className="pb-2">
              <CardTitle className="text-sm flex items-center gap-2">
                <Tag className="w-4 h-4 text-emerald-400" /> EDAM Operations
              </CardTitle>
            </CardHeader>
            <CardContent>
              {(data?.operations?.length ?? 0) > 0 ? (
                <div className="flex flex-wrap gap-1">
                  {data!.operations.map(op => (
                    <Link key={op.op_edam_id} href={`/bioskills-index/${id}/edam/${op.op_edam_id}`}>
                      <Badge variant="outline" className="text-xs hover:border-emerald-500/50 cursor-pointer text-emerald-300">
                        {op.op_name}
                      </Badge>
                    </Link>
                  ))}
                </div>
              ) : (
                <p className="text-xs text-muted-foreground">No operations annotated.</p>
              )}
            </CardContent>
          </Card>

          {/* EDAM Topics */}
          <Card className="border-border">
            <CardHeader className="pb-2">
              <CardTitle className="text-sm flex items-center gap-2">
                <Tag className="w-4 h-4 text-blue-400" /> EDAM Topics
              </CardTitle>
            </CardHeader>
            <CardContent>
              {(data?.topics?.length ?? 0) > 0 ? (
                <div className="flex flex-wrap gap-1">
                  {data!.topics.map(t => (
                    <Badge key={t.topic_edam_id} variant="outline" className="text-xs text-blue-300">
                      {t.topic_name}
                    </Badge>
                  ))}
                </div>
              ) : (
                <p className="text-xs text-muted-foreground">No topics annotated.</p>
              )}
            </CardContent>
          </Card>
        </div>

        {/* Code Snippets */}
        {(data?.snippets?.length ?? 0) > 0 && (
          <Card className="border-border">
            <CardHeader className="pb-2">
              <CardTitle className="text-sm flex items-center gap-2">
                <Code className="w-4 h-4 text-violet-400" /> Code Snippets
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-2">
              {data!.snippets.map(snip => (
                <div key={snip.id} className="border border-border rounded">
                  <button
                    onClick={() => setExpandedSnippet(expandedSnippet === snip.id ? null : snip.id)}
                    className="w-full flex items-center justify-between px-3 py-2 text-sm hover:bg-muted/50"
                  >
                    <div className="flex items-center gap-2">
                      <Badge variant="outline" className="text-xs">{snip.snippet_type}</Badge>
                      <Badge variant="outline" className="text-xs text-violet-400">{snip.language}</Badge>
                      <span className="text-muted-foreground">{snip.name}</span>
                    </div>
                    <span className="text-xs text-muted-foreground">{expandedSnippet === snip.id ? '▲' : '▼'}</span>
                  </button>
                  {expandedSnippet === snip.id && (
                    <pre className="p-3 text-xs bg-muted/30 overflow-x-auto border-t border-border font-mono">
                      {snip.content}
                    </pre>
                  )}
                </div>
              ))}
            </CardContent>
          </Card>
        )}
      </div>
    </div>
  );
}
