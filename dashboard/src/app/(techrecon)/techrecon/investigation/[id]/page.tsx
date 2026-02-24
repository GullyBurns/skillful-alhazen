'use client';

import { useState, useEffect, useCallback } from 'react';
import { useParams } from 'next/navigation';
import Link from 'next/link';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { SystemsGrid } from '@/components/techrecon/systems-grid';
import { NotesList } from '@/components/techrecon/notes-list';
import {
  InvestigationStatusBadge,
  CategoryBadge,
  FormatBadge,
  TypeBadge,
} from '@/components/techrecon/badges';
import {
  ArrowLeft,
  RefreshCw,
  Target,
  Server,
  StickyNote,
  FileText,
  Lightbulb,
  Database,
  Puzzle,
} from 'lucide-react';

interface Investigation {
  id: string;
  name: string;
  description?: string;
  status: string;
  goal: string;
  created_at?: string;
}

interface System {
  id: string;
  name: string;
  repo_url?: string;
  language?: string;
  stars?: number;
  maturity?: string;
  description?: string;
  created_at?: string;
}

interface Artifact {
  id: string;
  name: string;
  source_uri?: string;
  mime_type?: string;
  created_at?: string;
}

interface Note {
  id: string;
  name: string;
  content: string;
  type?: string;
  priority?: string;
  complexity?: string;
  created_at?: string;
}

interface Component {
  id: string;
  name: string;
  type?: string;
  role?: string;
}

interface Concept {
  id: string;
  name: string;
  category?: string;
  description?: string;
}

interface DataModel {
  id: string;
  name: string;
  format?: string;
  description?: string;
}

interface Summary {
  systems_count: number;
  artifacts_count: number;
  notes_count: number;
  components_count: number;
  concepts_count: number;
  data_models_count: number;
}

export default function InvestigationDetailPage() {
  const { id } = useParams<{ id: string }>();
  const [investigation, setInvestigation] = useState<Investigation | null>(null);
  const [systems, setSystems] = useState<System[]>([]);
  const [artifacts, setArtifacts] = useState<Artifact[]>([]);
  const [notes, setNotes] = useState<Note[]>([]);
  const [components, setComponents] = useState<Component[]>([]);
  const [concepts, setConcepts] = useState<Concept[]>([]);
  const [dataModels, setDataModels] = useState<DataModel[]>([]);
  const [summary, setSummary] = useState<Summary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchData = useCallback(async () => {
    if (!id) return;
    setLoading(true);
    setError(null);

    try {
      const res = await fetch(`/api/techrecon/investigation/${id}`);
      if (!res.ok) throw new Error('Failed to fetch investigation');
      const data = await res.json();

      if (!data.success) {
        setError(data.error || 'Investigation not found');
        return;
      }

      setInvestigation(data.investigation);
      setSystems(data.systems || []);
      setArtifacts(data.artifacts || []);
      setNotes(data.notes || []);
      setComponents(data.components || []);
      setConcepts(data.concepts || []);
      setDataModels(data.data_models || []);
      setSummary(data.summary || null);
    } catch (err) {
      console.error('Fetch error:', err);
      setError(err instanceof Error ? err.message : 'Failed to load data');
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <RefreshCw className="w-6 h-6 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (error || !investigation) {
    return (
      <div className="min-h-screen">
        <header className="border-b border-border/50 bg-card/50 backdrop-blur-sm">
          <div className="container mx-auto px-4 py-4">
            <Link
              href="/techrecon"
              className="flex items-center gap-2 text-sm text-muted-foreground hover:text-primary transition-colors"
            >
              <ArrowLeft className="w-4 h-4" />
              Back to TechRecon
            </Link>
          </div>
        </header>
        <main className="container mx-auto px-4 py-12 text-center">
          <p className="text-destructive">{error || 'Investigation not found'}</p>
        </main>
      </div>
    );
  }

  return (
    <div className="min-h-screen">
      {/* Header */}
      <header className="border-b border-border/50 bg-card/50 backdrop-blur-sm">
        <div className="container mx-auto px-4 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-6">
              <Link
                href="/techrecon"
                className="flex items-center gap-2 text-sm text-muted-foreground hover:text-primary transition-colors"
              >
                <ArrowLeft className="w-4 h-4" />
                TechRecon
              </Link>
              <div>
                <div className="flex items-center gap-3">
                  <h1 className="text-2xl font-bold bg-gradient-to-r from-cyan-400 to-blue-400 bg-clip-text text-transparent">
                    {investigation.name}
                  </h1>
                  <InvestigationStatusBadge status={investigation.status} />
                </div>
                {investigation.created_at && (
                  <p className="text-xs text-muted-foreground mt-1">
                    Started {new Date(investigation.created_at).toLocaleDateString()}
                  </p>
                )}
              </div>
            </div>
            <Button
              variant="outline"
              size="sm"
              onClick={fetchData}
              className="border-border/50 hover:border-primary/50 hover:bg-primary/10"
            >
              <RefreshCw className="w-4 h-4 mr-2" />
              Refresh
            </Button>
          </div>
        </div>
      </header>

      <main className="container mx-auto px-4 py-6 space-y-6">
        {/* Purpose Section */}
        {investigation.goal && (
          <Card className="border-primary/30 bg-primary/5">
            <CardContent className="pt-4 pb-4">
              <div className="flex items-start gap-3">
                <Target className="w-5 h-5 text-primary shrink-0 mt-0.5" />
                <div>
                  <p className="text-sm font-medium text-primary mb-1">Purpose</p>
                  <p className="text-sm">{investigation.goal}</p>
                </div>
              </div>
            </CardContent>
          </Card>
        )}

        {/* Description */}
        {investigation.description && (
          <p className="text-sm text-muted-foreground">{investigation.description}</p>
        )}

        {/* Stats Bar */}
        {summary && (
          <div className="flex items-center gap-6 text-sm text-muted-foreground">
            <span className="flex items-center gap-1.5">
              <Server className="w-4 h-4" />
              {summary.systems_count} systems
            </span>
            <span className="flex items-center gap-1.5">
              <StickyNote className="w-4 h-4" />
              {summary.notes_count} notes
            </span>
            <span className="flex items-center gap-1.5">
              <FileText className="w-4 h-4" />
              {summary.artifacts_count} artifacts
            </span>
            <span className="flex items-center gap-1.5">
              <Puzzle className="w-4 h-4" />
              {summary.components_count} components
            </span>
            <span className="flex items-center gap-1.5">
              <Lightbulb className="w-4 h-4" />
              {summary.concepts_count} concepts
            </span>
            <span className="flex items-center gap-1.5">
              <Database className="w-4 h-4" />
              {summary.data_models_count} data models
            </span>
          </div>
        )}

        {/* Two-Column Layout */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Left Column (2/3) */}
          <div className="lg:col-span-2 space-y-6">
            {/* Systems */}
            <section>
              <h2 className="text-sm font-semibold mb-3 flex items-center gap-2">
                <Server className="w-4 h-4" />
                Systems
              </h2>
              <SystemsGrid systems={systems} />
            </section>

            {/* Notes */}
            {notes.length > 0 && (
              <section>
                <h2 className="text-sm font-semibold mb-3 flex items-center gap-2">
                  <StickyNote className="w-4 h-4" />
                  Notes
                </h2>
                <NotesList notes={notes} grouped={true} />
              </section>
            )}
          </div>

          {/* Right Column (1/3) */}
          <div className="space-y-6">
            {/* Artifacts */}
            {artifacts.length > 0 && (
              <Card>
                <CardHeader className="pb-2">
                  <CardTitle className="text-sm flex items-center gap-2">
                    <FileText className="w-4 h-4" />
                    Artifacts
                    <Badge variant="secondary" className="ml-auto">
                      {artifacts.length}
                    </Badge>
                  </CardTitle>
                </CardHeader>
                <CardContent className="space-y-2">
                  {artifacts.map((a) => (
                    <Link
                      key={a.id}
                      href={`/techrecon/artifact/${a.id}`}
                      className="flex items-center gap-2 text-sm hover:text-primary transition-colors py-1"
                    >
                      <span className="truncate">{a.name}</span>
                      {a.mime_type && (
                        <TypeBadge type={a.mime_type.split('/').pop() || a.mime_type} />
                      )}
                    </Link>
                  ))}
                </CardContent>
              </Card>
            )}

            {/* Components */}
            {components.length > 0 && (
              <Card>
                <CardHeader className="pb-2">
                  <CardTitle className="text-sm flex items-center gap-2">
                    <Puzzle className="w-4 h-4" />
                    Components
                    <Badge variant="secondary" className="ml-auto">
                      {components.length}
                    </Badge>
                  </CardTitle>
                </CardHeader>
                <CardContent className="space-y-2">
                  {components.map((c) => (
                    <Link
                      key={c.id}
                      href={`/techrecon/component/${c.id}`}
                      className="flex items-center gap-2 text-sm hover:text-primary transition-colors py-1"
                    >
                      <span className="truncate">{c.name}</span>
                      {c.type && (
                        <Badge variant="outline" className="text-xs shrink-0">
                          {c.type}
                        </Badge>
                      )}
                    </Link>
                  ))}
                </CardContent>
              </Card>
            )}

            {/* Concepts */}
            {concepts.length > 0 && (
              <Card>
                <CardHeader className="pb-2">
                  <CardTitle className="text-sm flex items-center gap-2">
                    <Lightbulb className="w-4 h-4" />
                    Concepts
                    <Badge variant="secondary" className="ml-auto">
                      {concepts.length}
                    </Badge>
                  </CardTitle>
                </CardHeader>
                <CardContent className="space-y-2">
                  {concepts.map((c) => (
                    <Link
                      key={c.id}
                      href={`/techrecon/concept/${c.id}`}
                      className="flex items-center gap-2 text-sm hover:text-primary transition-colors py-1"
                    >
                      <span className="truncate">{c.name}</span>
                      {c.category && <CategoryBadge category={c.category} />}
                    </Link>
                  ))}
                </CardContent>
              </Card>
            )}

            {/* Data Models */}
            {dataModels.length > 0 && (
              <Card>
                <CardHeader className="pb-2">
                  <CardTitle className="text-sm flex items-center gap-2">
                    <Database className="w-4 h-4" />
                    Data Models
                    <Badge variant="secondary" className="ml-auto">
                      {dataModels.length}
                    </Badge>
                  </CardTitle>
                </CardHeader>
                <CardContent className="space-y-2">
                  {dataModels.map((dm) => (
                    <div
                      key={dm.id}
                      className="flex items-center gap-2 text-sm py-1"
                    >
                      <span className="truncate">{dm.name}</span>
                      {dm.format && <FormatBadge format={dm.format} />}
                    </div>
                  ))}
                </CardContent>
              </Card>
            )}
          </div>
        </div>
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
