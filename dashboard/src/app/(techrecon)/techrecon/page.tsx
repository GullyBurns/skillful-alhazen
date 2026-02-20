'use client';

import { useState, useEffect, useCallback } from 'react';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { StatsOverview } from '@/components/techrecon/stats-overview';
import { SystemsGrid } from '@/components/techrecon/systems-grid';
import { CategoryBadge, FormatBadge, TypeBadge } from '@/components/techrecon/badges';
import {
  RefreshCw,
  Server,
  Lightbulb,
  Database,
  FileText,
  StickyNote,
  ArrowLeft,
} from 'lucide-react';
import Link from 'next/link';

interface Investigation {
  id: string;
  name: string;
  status: string;
  goal: string;
  created_at: string;
}

interface System {
  id: string;
  name: string;
  repo_url?: string;
  language?: string;
  stars?: number;
  maturity?: string;
  created_at?: string;
}

interface Artifact {
  id: string;
  name: string;
  type: string;
  source_uri?: string;
  mime_type?: string;
  created_at?: string;
  status?: string;
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
type Concept = any;
// eslint-disable-next-line @typescript-eslint/no-explicit-any
type DataModel = any;
// eslint-disable-next-line @typescript-eslint/no-explicit-any
type Note = any;

export default function TechReconDashboard() {
  const [investigations, setInvestigations] = useState<Investigation[]>([]);
  const [systems, setSystems] = useState<System[]>([]);
  const [artifacts, setArtifacts] = useState<Artifact[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedInvestigation, setSelectedInvestigation] = useState<string>('all');
  // Data loaded on tab switch
  const [concepts, setConcepts] = useState<Concept[]>([]);
  const [dataModels, setDataModels] = useState<DataModel[]>([]);
  const [notes, setNotes] = useState<Note[]>([]);
  const [conceptsLoaded, setConceptsLoaded] = useState(false);
  const [dataModelsLoaded, setDataModelsLoaded] = useState(false);
  const [notesLoaded, setNotesLoaded] = useState(false);

  const fetchData = useCallback(async () => {
    setLoading(true);
    setError(null);

    try {
      const [invRes, sysRes, artRes] = await Promise.all([
        fetch('/api/techrecon/investigations'),
        fetch('/api/techrecon/systems'),
        fetch('/api/techrecon/artifacts'),
      ]);

      if (!invRes.ok || !sysRes.ok || !artRes.ok) {
        throw new Error('Failed to fetch data');
      }

      const [invData, sysData, artData] = await Promise.all([
        invRes.json(),
        sysRes.json(),
        artRes.json(),
      ]);

      setInvestigations(invData.investigations || []);
      setSystems(sysData.systems || []);
      setArtifacts(artData.artifacts || []);
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

  // Lazy-load concepts/data-models/notes on tab click
  // These require aggregation across all systems, so we fetch per-system and merge
  const fetchSystemDetails = useCallback(async (target: 'concepts' | 'dataModels' | 'notes') => {
    if (systems.length === 0) return;
    try {
      const results = await Promise.all(
        systems.map(async (sys) => {
          const res = await fetch(`/api/techrecon/system/${sys.id}`);
          if (!res.ok) return null;
          return res.json();
        })
      );

      const allConcepts: Concept[] = [];
      const allDataModels: DataModel[] = [];
      const allNotes: Note[] = [];
      const seenConcepts = new Set<string>();
      const seenModels = new Set<string>();

      for (const data of results) {
        if (!data || !data.success) continue;

        if (target === 'concepts' || !conceptsLoaded) {
          for (const comp of data.components || []) {
            for (const concept of comp.concepts || []) {
              if (!seenConcepts.has(concept.id)) {
                seenConcepts.add(concept.id);
                allConcepts.push({ ...concept, system_name: data.system?.name });
              }
            }
          }
        }

        if (target === 'dataModels' || !dataModelsLoaded) {
          for (const dm of data.data_models || []) {
            if (!seenModels.has(dm.id)) {
              seenModels.add(dm.id);
              allDataModels.push({ ...dm, system_name: data.system?.name });
            }
          }
        }

        if (target === 'notes' || !notesLoaded) {
          for (const note of data.notes || []) {
            allNotes.push({ ...note, system_name: data.system?.name });
          }
        }
      }

      if (!conceptsLoaded || target === 'concepts') {
        setConcepts(allConcepts);
        setConceptsLoaded(true);
      }
      if (!dataModelsLoaded || target === 'dataModels') {
        setDataModels(allDataModels);
        setDataModelsLoaded(true);
      }
      if (!notesLoaded || target === 'notes') {
        setNotes(allNotes);
        setNotesLoaded(true);
      }
    } catch (err) {
      console.error('System details error:', err);
    }
  }, [systems, conceptsLoaded, dataModelsLoaded, notesLoaded]);

  const handleTabChange = (value: string) => {
    if (value === 'concepts' && !conceptsLoaded) fetchSystemDetails('concepts');
    if (value === 'data-models' && !dataModelsLoaded) fetchSystemDetails('dataModels');
    if (value === 'notes' && !notesLoaded) fetchSystemDetails('notes');
  };

  // Stats
  const stats = {
    systems: systems.length,
    components: 0, // Will be populated when system details are loaded
    concepts: concepts.length,
    artifacts: artifacts.length,
    notes: notes.length,
    investigations: investigations.length,
  };

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
                  TechRecon Dashboard
                </h1>
                <p className="text-sm text-muted-foreground">
                  Explore technology reconnaissance investigations
                </p>
              </div>
            </div>
            <div className="flex items-center gap-4">
              {investigations.length > 0 && (
                <Select value={selectedInvestigation} onValueChange={setSelectedInvestigation}>
                  <SelectTrigger className="w-[220px]">
                    <SelectValue placeholder="Investigation" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">All Investigations</SelectItem>
                    {investigations.map((inv) => (
                      <SelectItem key={inv.id} value={inv.id}>
                        {inv.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              )}
              <Badge variant="outline" className="text-xs border-primary/30 text-primary">
                TypeDB Connected
              </Badge>
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
        </div>
      </header>

      <main className="container mx-auto px-4 py-6 space-y-6">
        {/* Error Alert */}
        {error && (
          <div className="bg-destructive/10 text-destructive px-4 py-3 rounded-lg">
            <strong>Error:</strong> {error}
            <p className="text-sm mt-1">
              Make sure TypeDB is running and the techrecon skill is configured.
            </p>
          </div>
        )}

        {/* Stats Overview */}
        <StatsOverview {...stats} />

        {/* Main Content Tabs */}
        <Tabs defaultValue="systems" className="space-y-4" onValueChange={handleTabChange}>
          <TabsList>
            <TabsTrigger value="systems" className="flex items-center gap-2">
              <Server className="w-4 h-4" />
              Systems
            </TabsTrigger>
            <TabsTrigger value="concepts" className="flex items-center gap-2">
              <Lightbulb className="w-4 h-4" />
              Concepts
            </TabsTrigger>
            <TabsTrigger value="data-models" className="flex items-center gap-2">
              <Database className="w-4 h-4" />
              Data Models
            </TabsTrigger>
            <TabsTrigger value="artifacts" className="flex items-center gap-2">
              <FileText className="w-4 h-4" />
              Artifacts
            </TabsTrigger>
            <TabsTrigger value="notes" className="flex items-center gap-2">
              <StickyNote className="w-4 h-4" />
              Notes
            </TabsTrigger>
          </TabsList>

          {/* Systems Tab */}
          <TabsContent value="systems">
            {loading ? (
              <div className="flex items-center justify-center py-12">
                <RefreshCw className="w-6 h-6 animate-spin text-muted-foreground" />
              </div>
            ) : (
              <SystemsGrid systems={systems} />
            )}
          </TabsContent>

          {/* Concepts Tab */}
          <TabsContent value="concepts">
            {!conceptsLoaded ? (
              <div className="flex items-center justify-center py-12">
                <RefreshCw className="w-6 h-6 animate-spin text-muted-foreground" />
              </div>
            ) : (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Name</TableHead>
                    <TableHead>Category</TableHead>
                    <TableHead>System</TableHead>
                    <TableHead>Description</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {concepts.map((concept: Concept) => (
                    <TableRow key={concept.id}>
                      <TableCell>
                        <Link
                          href={`/techrecon/concept/${concept.id}`}
                          className="text-primary hover:underline font-medium"
                        >
                          {concept.name}
                        </Link>
                      </TableCell>
                      <TableCell>
                        {concept.category && <CategoryBadge category={concept.category} />}
                      </TableCell>
                      <TableCell className="text-muted-foreground text-sm">
                        {concept.system_name}
                      </TableCell>
                      <TableCell className="text-sm text-muted-foreground max-w-xs truncate">
                        {concept.description}
                      </TableCell>
                    </TableRow>
                  ))}
                  {concepts.length === 0 && (
                    <TableRow>
                      <TableCell colSpan={4} className="text-center text-muted-foreground py-8">
                        No concepts found.
                      </TableCell>
                    </TableRow>
                  )}
                </TableBody>
              </Table>
            )}
          </TabsContent>

          {/* Data Models Tab */}
          <TabsContent value="data-models">
            {!dataModelsLoaded ? (
              <div className="flex items-center justify-center py-12">
                <RefreshCw className="w-6 h-6 animate-spin text-muted-foreground" />
              </div>
            ) : (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Name</TableHead>
                    <TableHead>Format</TableHead>
                    <TableHead>System</TableHead>
                    <TableHead>Description</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {dataModels.map((dm: DataModel) => (
                    <TableRow key={dm.id}>
                      <TableCell className="font-medium">{dm.name}</TableCell>
                      <TableCell>
                        {dm.format && <FormatBadge format={dm.format} />}
                      </TableCell>
                      <TableCell className="text-muted-foreground text-sm">
                        {dm.system_name}
                      </TableCell>
                      <TableCell className="text-sm text-muted-foreground max-w-xs truncate">
                        {dm.description}
                      </TableCell>
                    </TableRow>
                  ))}
                  {dataModels.length === 0 && (
                    <TableRow>
                      <TableCell colSpan={4} className="text-center text-muted-foreground py-8">
                        No data models found.
                      </TableCell>
                    </TableRow>
                  )}
                </TableBody>
              </Table>
            )}
          </TabsContent>

          {/* Artifacts Tab */}
          <TabsContent value="artifacts">
            {loading ? (
              <div className="flex items-center justify-center py-12">
                <RefreshCw className="w-6 h-6 animate-spin text-muted-foreground" />
              </div>
            ) : (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Name</TableHead>
                    <TableHead>Type</TableHead>
                    <TableHead>MIME Type</TableHead>
                    <TableHead>Created</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {artifacts.map((artifact) => (
                    <TableRow key={artifact.id}>
                      <TableCell>
                        <Link
                          href={`/techrecon/artifact/${artifact.id}`}
                          className="text-primary hover:underline font-medium"
                        >
                          {artifact.name}
                        </Link>
                      </TableCell>
                      <TableCell>
                        {artifact.type && <TypeBadge type={artifact.type} />}
                      </TableCell>
                      <TableCell className="text-sm text-muted-foreground">
                        {artifact.mime_type}
                      </TableCell>
                      <TableCell className="text-sm text-muted-foreground">
                        {artifact.created_at && new Date(artifact.created_at).toLocaleDateString()}
                      </TableCell>
                    </TableRow>
                  ))}
                  {artifacts.length === 0 && (
                    <TableRow>
                      <TableCell colSpan={4} className="text-center text-muted-foreground py-8">
                        No artifacts found.
                      </TableCell>
                    </TableRow>
                  )}
                </TableBody>
              </Table>
            )}
          </TabsContent>

          {/* Notes Tab */}
          <TabsContent value="notes">
            {!notesLoaded ? (
              <div className="flex items-center justify-center py-12">
                <RefreshCw className="w-6 h-6 animate-spin text-muted-foreground" />
              </div>
            ) : (
              <div className="space-y-4">
                {notes.map((note: Note, idx: number) => (
                  <div key={note.id || idx} className="border border-border/50 rounded-lg p-4">
                    <div className="flex items-center gap-2 mb-2">
                      <span className="font-medium text-sm">{note.name}</span>
                      {note.type && <TypeBadge type={note.type} />}
                      <span className="text-xs text-muted-foreground ml-auto">
                        {note.system_name}
                      </span>
                    </div>
                    {note.content && (
                      <p className="text-sm text-muted-foreground line-clamp-3">
                        {note.content.substring(0, 300)}
                        {note.content.length > 300 ? '...' : ''}
                      </p>
                    )}
                  </div>
                ))}
                {notes.length === 0 && (
                  <p className="text-center text-muted-foreground py-8">No notes found.</p>
                )}
              </div>
            )}
          </TabsContent>
        </Tabs>
      </main>

      {/* Footer */}
      <footer className="border-t border-border/50 mt-8">
        <div className="container mx-auto px-4 py-4">
          <p className="text-xs text-muted-foreground text-center">
            TechRecon Dashboard &bull; Powered by TypeDB + Next.js
          </p>
        </div>
      </footer>
    </div>
  );
}
