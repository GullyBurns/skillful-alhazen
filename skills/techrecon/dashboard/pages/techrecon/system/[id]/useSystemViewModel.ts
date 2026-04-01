'use client';

import { useState, useEffect, useCallback } from 'react';
import type { Paper } from '@/components/techrecon/types';

export type { Paper };

export interface SystemDetail {
  id: string;
  name: string;
  description?: string;
  repo_url?: string;
  doc_url?: string;
  language?: string;
  maturity?: string;
  stars?: number;
  license?: string;
  version?: string;
  last_commit?: string;
  base_model?: string;
  model_architecture?: string;
}

export interface Note {
  id: string;
  name: string;
  content: string;
  type?: string;
  priority?: string;
}

export interface SystemViewModel {
  loading: boolean;
  error: string | null;
  system: SystemDetail | null;
  components: unknown[];
  architectureNote: Note | null;
  assessmentNote: Note | null;
  otherNotes: Note[];
  literaturePapers: Paper[];
  benchmarks: unknown[];
  decisions: unknown[];
  workflows: unknown[];
  artifacts: unknown[];
  tags: string[];
}

export function useSystemViewModel(id: string | undefined): SystemViewModel {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [system, setSystem] = useState<SystemDetail | null>(null);
  const [components, setComponents] = useState<unknown[]>([]);
  const [notes, setNotes] = useState<Note[]>([]);
  const [literaturePapers, setLiteraturePapers] = useState<Paper[]>([]);
  const [benchmarks, setBenchmarks] = useState<unknown[]>([]);
  const [decisions, setDecisions] = useState<unknown[]>([]);
  const [workflows, setWorkflows] = useState<unknown[]>([]);
  const [artifacts, setArtifacts] = useState<unknown[]>([]);
  const [tags, setTags] = useState<string[]>([]);

  const fetchData = useCallback(async () => {
    if (!id) return;
    setLoading(true);
    setError(null);

    try {
      const [sysRes, benchRes, decRes, wfRes, papersRes] = await Promise.all([
        fetch(`/api/techrecon/system/${id}`),
        fetch(`/api/techrecon/benchmarks/${id}`),
        fetch(`/api/techrecon/decisions/${id}`),
        fetch(`/api/techrecon/workflows?system=${id}`),
        fetch(`/api/techrecon/papers?system=${id}`),
      ]);

      if (!sysRes.ok) throw new Error('Failed to fetch system');
      const sysJson = await sysRes.json();
      setSystem(sysJson.system || sysJson);
      setComponents(sysJson.components || []);
      setNotes(sysJson.notes || []);
      setArtifacts(sysJson.artifacts || []);
      setTags(sysJson.tags || []);

      if (benchRes.ok) {
        const d = await benchRes.json();
        setBenchmarks(d.benchmarks || []);
      }
      if (decRes.ok) {
        const d = await decRes.json();
        setDecisions(d.decisions || []);
      }
      if (wfRes.ok) {
        const d = await wfRes.json();
        setWorkflows(d.workflows || []);
      }
      if (papersRes.ok) {
        const d = await papersRes.json();
        setLiteraturePapers(d.papers || []);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const architectureNote = notes.find((n) => n.type === 'architecture') ?? null;
  const assessmentNote = notes.find((n) => n.type === 'assessment') ?? null;
  const otherNotes = notes.filter(
    (n) => n.type !== 'architecture' && n.type !== 'assessment'
  );

  return {
    loading,
    error,
    system,
    components,
    architectureNote,
    assessmentNote,
    otherNotes,
    literaturePapers,
    benchmarks,
    decisions,
    workflows,
    artifacts,
    tags,
  };
}
