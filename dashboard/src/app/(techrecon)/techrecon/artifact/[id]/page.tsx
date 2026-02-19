'use client';

import { useState, useEffect, use } from 'react';
import Link from 'next/link';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { ArrowLeft, ExternalLink, RefreshCw, FileText } from 'lucide-react';
import { TypeBadge } from '@/components/techrecon/badges';
import { ArtifactViewer } from '@/components/techrecon/artifact-viewer';

interface ArtifactPageProps {
  params: Promise<{ id: string }>;
}

export default function ArtifactPage({ params }: ArtifactPageProps) {
  const { id } = use(params);
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function fetchArtifact() {
      setLoading(true);
      setError(null);
      try {
        const res = await fetch(`/api/techrecon/artifact/${id}`);
        if (!res.ok) throw new Error('Failed to fetch artifact');
        const json = await res.json();
        setData(json);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Unknown error');
      } finally {
        setLoading(false);
      }
    }
    fetchArtifact();
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
          <strong>Error:</strong> {error || 'Artifact not found'}
        </div>
      </div>
    );
  }

  const artifact = data.artifact || {};
  const linkedEntity = data.linked_entity;

  return (
    <div className="min-h-screen">
      {/* Header */}
      <header className="border-b border-border/50 bg-card/50 backdrop-blur-sm">
        <div className="container mx-auto px-4 py-4">
          <Link href="/techrecon">
            <Button variant="ghost" size="sm" className="mb-2 hover:bg-primary/10">
              <ArrowLeft className="w-4 h-4 mr-2" />
              Back to TechRecon
            </Button>
          </Link>
          <div className="flex items-start justify-between">
            <div>
              <h1 className="text-2xl font-bold bg-gradient-to-r from-cyan-400 to-blue-400 bg-clip-text text-transparent flex items-center gap-3">
                <FileText className="w-6 h-6 text-cyan-400" />
                {artifact.name || 'Unknown Artifact'}
              </h1>
              <div className="flex items-center gap-2 mt-1">
                {artifact.mime_type && (
                  <span className="text-sm text-muted-foreground">{artifact.mime_type}</span>
                )}
                {artifact.file_size && (
                  <span className="text-sm text-muted-foreground">
                    ({(artifact.file_size / 1024).toFixed(1)} KB)
                  </span>
                )}
              </div>
            </div>
            <div className="flex items-center gap-2">
              {artifact.type && <TypeBadge type={artifact.type} />}
              {artifact.source_uri && (
                <a href={artifact.source_uri} target="_blank" rel="noopener noreferrer">
                  <Button variant="outline" size="sm">
                    <ExternalLink className="w-4 h-4 mr-2" />
                    Source
                  </Button>
                </a>
              )}
            </div>
          </div>
        </div>
      </header>

      <main className="container mx-auto px-4 py-6">
        <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
          {/* Content */}
          <div className="lg:col-span-3">
            <Card>
              <CardHeader>
                <CardTitle className="text-sm">Content</CardTitle>
              </CardHeader>
              <CardContent>
                <ArtifactViewer
                  content={artifact.content || ''}
                  mimeType={artifact.mime_type}
                />
              </CardContent>
            </Card>
          </div>

          {/* Sidebar */}
          <div className="space-y-4">
            {linkedEntity && (
              <Card>
                <CardHeader className="pb-3">
                  <CardTitle className="text-sm">Linked Entity</CardTitle>
                </CardHeader>
                <CardContent>
                  <Link
                    href={`/techrecon/system/${linkedEntity.id}`}
                    className="text-primary hover:underline text-sm font-medium"
                  >
                    {linkedEntity.name}
                  </Link>
                </CardContent>
              </Card>
            )}

            {artifact.created_at && (
              <Card>
                <CardContent className="p-4">
                  <p className="text-xs text-muted-foreground">Created</p>
                  <p className="text-sm font-medium">
                    {new Date(artifact.created_at).toLocaleString()}
                  </p>
                </CardContent>
              </Card>
            )}

            {artifact.storage && (
              <Card>
                <CardContent className="p-4">
                  <p className="text-xs text-muted-foreground">Storage</p>
                  <p className="text-sm font-medium">{artifact.storage}</p>
                </CardContent>
              </Card>
            )}
          </div>
        </div>
      </main>
    </div>
  );
}
