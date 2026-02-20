'use client';

import { useState, useEffect, use } from 'react';
import Link from 'next/link';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Separator } from '@/components/ui/separator';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { ArrowLeft, RefreshCw, Puzzle, Server } from 'lucide-react';
import { CategoryBadge, TypeBadge } from '@/components/techrecon/badges';

interface ComponentPageProps {
  params: Promise<{ id: string }>;
}

export default function ComponentPage({ params }: ComponentPageProps) {
  const { id } = use(params);
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function fetchComponent() {
      setLoading(true);
      setError(null);
      try {
        const res = await fetch(`/api/techrecon/component/${id}`);
        if (!res.ok) throw new Error('Failed to fetch component');
        const json = await res.json();
        setData(json);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Unknown error');
      } finally {
        setLoading(false);
      }
    }
    fetchComponent();
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
          <strong>Error:</strong> {error || 'Component not found'}
        </div>
      </div>
    );
  }

  const component = data.component || {};
  const system = data.system;
  const concepts = data.concepts || [];
  const notes = data.notes || [];

  return (
    <div className="min-h-screen">
      {/* Header */}
      <header className="border-b border-border/50 bg-card/50 backdrop-blur-sm">
        <div className="container mx-auto px-4 py-4">
          {system && (
            <Link href={`/techrecon/system/${system.id}`}>
              <Button variant="ghost" size="sm" className="mb-2 hover:bg-primary/10">
                <ArrowLeft className="w-4 h-4 mr-2" />
                Back to {system.name}
              </Button>
            </Link>
          )}
          <div className="flex items-start justify-between">
            <div>
              <h1 className="text-2xl font-bold bg-gradient-to-r from-cyan-400 to-blue-400 bg-clip-text text-transparent flex items-center gap-3">
                <Puzzle className="w-6 h-6 text-purple-400" />
                {component.name || 'Unknown Component'}
              </h1>
              {component.description && (
                <p className="text-sm text-muted-foreground mt-1 max-w-2xl">
                  {component.description}
                </p>
              )}
            </div>
            <div className="flex items-center gap-2">
              {component.type && (
                <Badge variant="outline">{component.type}</Badge>
              )}
              {component.role && (
                <Badge variant="secondary">{component.role}</Badge>
              )}
            </div>
          </div>
          {system && (
            <div className="flex items-center gap-2 mt-2 text-sm text-muted-foreground">
              <Server className="w-4 h-4" />
              <Link href={`/techrecon/system/${system.id}`} className="text-primary hover:underline">
                {system.name}
              </Link>
            </div>
          )}
          {component.file_path && (
            <p className="text-xs text-muted-foreground font-mono mt-1">
              {component.file_path}
            </p>
          )}
        </div>
      </header>

      <main className="container mx-auto px-4 py-6 space-y-6">
        {/* Concepts */}
        {concepts.length > 0 && (
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                Concepts
                <Badge variant="secondary" className="ml-auto">
                  {concepts.length}
                </Badge>
              </CardTitle>
            </CardHeader>
            <CardContent>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Name</TableHead>
                    <TableHead>Category</TableHead>
                    <TableHead>Description</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {/* eslint-disable-next-line @typescript-eslint/no-explicit-any */}
                  {concepts.map((concept: any) => (
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
                      <TableCell className="text-sm text-muted-foreground max-w-xs truncate">
                        {concept.description}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </CardContent>
          </Card>
        )}

        {/* Notes */}
        {notes.length > 0 && (
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                Notes
                <Badge variant="secondary" className="ml-auto">
                  {notes.length}
                </Badge>
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              {/* eslint-disable-next-line @typescript-eslint/no-explicit-any */}
              {notes.map((note: any, idx: number) => (
                <div key={note.id || idx} className="text-sm">
                  <div className="flex items-center gap-2 mb-1">
                    {note.name && <span className="font-medium">{note.name}</span>}
                    {note.type && <TypeBadge type={note.type} />}
                  </div>
                  {note.content && (
                    <div className="prose prose-sm max-w-none dark:prose-invert">
                      <ReactMarkdown remarkPlugins={[remarkGfm]}>
                        {note.content}
                      </ReactMarkdown>
                    </div>
                  )}
                  {idx < notes.length - 1 && <Separator className="mt-3" />}
                </div>
              ))}
            </CardContent>
          </Card>
        )}
      </main>
    </div>
  );
}
