'use client';

import { useState, useEffect, use } from 'react';
import Link from 'next/link';
import { ExternalLink, Tag, Code, ArrowDownToLine, ArrowUpFromLine, Cpu, Clock, MemoryStick } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';

const linkClass =
  'text-cyan-400 font-semibold underline underline-offset-2 hover:text-blue-400 transition-colors';

type SkillDetail = {
  id: string;
  name: string;
  description: string;
  type: string;
  status: string;
  source_repo: string;
  source_file: string;
  github_url: string;
  tool_access: string;
  cluster_label: string;
  cluster_id: number;
  umap_x: number;
  umap_y: number;
  requires_gpu: boolean | null;
  runtime_class: string | null;
  memory_class: string | null;
  language: string | null;
};

type DataTerm = { data_name: string; data_edam_id: string };

type ShowSkillResponse = {
  success: boolean;
  skill: SkillDetail;
  operations: Array<{ op_edam_id: string; op_name: string; op_source: string }>;
  topics: Array<{ topic_edam_id: string; topic_name: string }>;
  inputs: DataTerm[];
  outputs: DataTerm[];
  snippets: Array<{ snippet_id: string; snippet_name: string; snippet_content: string; snippet_type: string; snippet_lang: string }>;
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

  const hasProfile = skill.requires_gpu !== null || skill.runtime_class || skill.memory_class || skill.language;
  const hasInputsOrOutputs = (data?.inputs?.length ?? 0) > 0 || (data?.outputs?.length ?? 0) > 0;

  return (
    <div className="min-h-screen bg-background text-foreground p-6">
      <div className="max-w-4xl mx-auto">
        {/* Breadcrumb */}
        <div className="flex items-center gap-2 mb-6 text-sm flex-wrap">
          <Link href="/" className={linkClass}>Hub</Link>
          <span className="text-muted-foreground">/</span>
          <Link href="/bioskills-index" className={linkClass}>Bioskills Index</Link>
          <span className="text-muted-foreground">/</span>
          <Link href={`/bioskills-index/${id}`} className={linkClass + ' font-mono'}>{id.slice(0, 14)}…</Link>
          <span className="text-muted-foreground">/</span>
          <span className="text-muted-foreground truncate">{skill.name}</span>
        </div>

        <h1 className="text-2xl font-bold mb-4">{skill.name}</h1>

        {/* Provenance card */}
        <Card className="border-border mb-5">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm text-muted-foreground font-normal">Provenance</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <div className="flex flex-wrap gap-2">
              {skill.type && <Badge variant="outline" className="text-xs">{skill.type}</Badge>}
              {skill.status && (
                <Badge variant="outline" className={`text-xs ${skill.status === 'active' ? 'text-green-400 border-green-500/30' : ''}`}>
                  {skill.status}
                </Badge>
              )}
              {skill.cluster_label && (
                <Badge variant="outline" className="text-xs text-emerald-400 border-emerald-500/30">
                  {skill.cluster_label}
                </Badge>
              )}
              {skill.requires_gpu && (
                <Badge variant="outline" className="text-xs text-violet-400 border-violet-500/30 flex items-center gap-1">
                  <Cpu className="w-3 h-3" /> GPU
                </Badge>
              )}
              {skill.runtime_class && (
                <Badge variant="outline" className="text-xs text-blue-400 border-blue-500/30 flex items-center gap-1">
                  <Clock className="w-3 h-3" /> {skill.runtime_class}
                </Badge>
              )}
              {skill.memory_class && (
                <Badge variant="outline" className="text-xs text-orange-400 border-orange-500/30 flex items-center gap-1">
                  <MemoryStick className="w-3 h-3" /> {skill.memory_class}
                </Badge>
              )}
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-sm">
              {skill.language && (
                <div>
                  <span className="text-muted-foreground text-xs">Language</span>
                  <div className="font-medium">{skill.language}</div>
                </div>
              )}
              {skill.tool_access && (
                <div>
                  <span className="text-muted-foreground text-xs">Library / Tool</span>
                  <div className="font-medium font-mono">{skill.tool_access}</div>
                </div>
              )}
              {skill.source_repo && (
                <div>
                  <span className="text-muted-foreground text-xs">Source Repo</span>
                  <div>
                    <a href={skill.source_repo} target="_blank" rel="noopener noreferrer"
                      className={linkClass + ' text-sm flex items-center gap-1'}>
                      {skill.source_repo.replace('https://github.com/', '')}
                      <ExternalLink className="w-3 h-3" />
                    </a>
                  </div>
                </div>
              )}
              {skill.source_file && (
                <div>
                  <span className="text-muted-foreground text-xs">Source File</span>
                  <div className="font-mono text-sm">{skill.source_file}</div>
                </div>
              )}
              {(skill.umap_x !== undefined && skill.umap_y !== undefined) && (
                <div>
                  <span className="text-muted-foreground text-xs">UMAP Position</span>
                  <div className="font-mono text-sm text-muted-foreground">
                    ({skill.umap_x?.toFixed(2)}, {skill.umap_y?.toFixed(2)})
                  </div>
                </div>
              )}
            </div>

            {skill.description && (
              <p className="text-sm text-muted-foreground border-t border-border pt-3">{skill.description}</p>
            )}
          </CardContent>
        </Card>

        {/* Inputs / Outputs card */}
        {hasInputsOrOutputs && (
          <Card className="border-border mb-5">
            <CardHeader className="pb-2">
              <CardTitle className="text-sm flex items-center gap-2">
                <ArrowDownToLine className="w-4 h-4 text-teal-400" /> Data Types
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              {(data?.inputs?.length ?? 0) > 0 && (
                <div>
                  <div className="flex items-center gap-1 text-xs text-muted-foreground mb-1">
                    <ArrowDownToLine className="w-3 h-3" /> Accepts as input
                  </div>
                  <div className="flex flex-wrap gap-1">
                    {data!.inputs.map(d => (
                      <Badge key={d.data_edam_id} variant="outline" className="text-xs text-teal-400 border-teal-500/30">
                        {d.data_name}
                      </Badge>
                    ))}
                  </div>
                </div>
              )}
              {(data?.outputs?.length ?? 0) > 0 && (
                <div>
                  <div className="flex items-center gap-1 text-xs text-muted-foreground mb-1">
                    <ArrowUpFromLine className="w-3 h-3" /> Produces as output
                  </div>
                  <div className="flex flex-wrap gap-1">
                    {data!.outputs.map(d => (
                      <Badge key={d.data_edam_id} variant="outline" className="text-xs text-cyan-400 border-cyan-500/30">
                        {d.data_name}
                      </Badge>
                    ))}
                  </div>
                </div>
              )}
            </CardContent>
          </Card>
        )}

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-5">
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
                <div key={snip.snippet_id} className="border border-border rounded">
                  <button
                    onClick={() => setExpandedSnippet(expandedSnippet === snip.snippet_id ? null : snip.snippet_id)}
                    className="w-full flex items-center justify-between px-3 py-2 text-sm hover:bg-muted/50"
                  >
                    <div className="flex items-center gap-2">
                      <Badge variant="outline" className={`text-xs ${snip.snippet_type === 'pseudocode' ? 'text-teal-400 border-teal-500/30' : ''}`}>
                        {snip.snippet_type}
                      </Badge>
                      <Badge variant="outline" className="text-xs text-violet-400">{snip.snippet_lang}</Badge>
                      <span className="text-muted-foreground">{snip.snippet_name}</span>
                    </div>
                    <span className="text-xs text-muted-foreground">{expandedSnippet === snip.snippet_id ? '▲' : '▼'}</span>
                  </button>
                  {expandedSnippet === snip.snippet_id && (
                    <pre className={`p-3 text-xs overflow-x-auto border-t border-border font-mono whitespace-pre-wrap ${
                      snip.snippet_type === 'pseudocode' ? 'bg-teal-950/20 leading-relaxed' : 'bg-muted/30'
                    }`}>
                      {snip.snippet_content || '(no content)'}
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
