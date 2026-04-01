'use client';

import { useState, useEffect, useCallback } from 'react';
import type { Stage, StageCounts, Paper } from '@/components/techrecon/types';

export type { Stage, StageCounts, Paper };

export interface Investigation {
  id: string;
  name: string;
  description?: string;
  status: string;
  goal: string;
  created_at?: string;
}

export interface System {
  id: string;
  name: string;
  repo_url?: string;
  language?: string;
  stars?: number;
  maturity?: string;
  description?: string;
}

export interface Note {
  id: string;
  name: string;
  content: string;
  type?: string;
  priority?: string;
  created_at?: string;
}

export interface RawMaterials {
  artifacts: number;
  components: number;
  concepts: number;
  dataModels: number;
}

const SYNTHESIS_NOTE_TYPES = new Set([
  'architecture',
  'harness',
  'assessment',
  'design-pattern',
  'literature-review',
  'comparison',
]);

function deriveStage(
  inv: Investigation,
  notes: Note[],
  components: number,
  concepts: number
): Stage {
  if (inv.status === 'complete') return 'done';
  if (notes.some((n) => n.type === 'architecture' || n.type === 'assessment' || n.type === 'harness' || n.type === 'literature-review')) return 'synthesis';
  if (components > 0 || concepts > 0) return 'analysis';
  return 'discovery';
}

export interface InvestigationViewModel {
  loading: boolean;
  error: string | null;
  investigation: Investigation | null;
  systems: System[];
  stage: Stage;
  stageCounts: StageCounts;
  keyFindings: Note[];
  literature: Paper[];
  rawMaterials: RawMaterials;
  refresh: () => void;
}

export function useInvestigationViewModel(id: string | undefined): InvestigationViewModel {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [investigation, setInvestigation] = useState<Investigation | null>(null);
  const [systems, setSystems] = useState<System[]>([]);
  const [notes, setNotes] = useState<Note[]>([]);
  const [rawMaterials, setRawMaterials] = useState<RawMaterials>({
    artifacts: 0,
    components: 0,
    concepts: 0,
    dataModels: 0,
  });
  const [literature, setLiterature] = useState<Paper[]>([]);

  const fetchData = useCallback(async () => {
    if (!id) return;
    setLoading(true);
    setError(null);

    try {
      const res = await fetch(`/api/techrecon/investigation/${id}`);
      if (!res.ok) throw new Error('Failed to fetch investigation');
      const data = await res.json();
      if (!data.success) throw new Error(data.error || 'Investigation not found');

      const inv: Investigation = data.investigation;
      const sysList: System[] = data.systems || [];
      const notesList: Note[] = data.notes || [];

      setInvestigation(inv);
      setSystems(sysList);
      setNotes(notesList);
      setRawMaterials({
        artifacts: data.summary?.artifacts_count ?? (data.artifacts || []).length,
        components: data.summary?.components_count ?? (data.components || []).length,
        concepts: data.summary?.concepts_count ?? (data.concepts || []).length,
        dataModels: data.summary?.data_models_count ?? (data.data_models || []).length,
      });

      // Fetch papers for all systems in parallel, deduplicate by id
      if (sysList.length > 0) {
        const paperResponses = await Promise.all(
          sysList.map((s) =>
            fetch(`/api/techrecon/papers?system=${s.id}`)
              .then((r) => r.json())
              .then((d) => (d.papers || []) as Paper[])
              .catch(() => [] as Paper[])
          )
        );
        const seen = new Set<string>();
        const merged: Paper[] = [];
        for (const papers of paperResponses) {
          for (const p of papers) {
            if (!seen.has(p.id)) {
              seen.add(p.id);
              merged.push(p);
            }
          }
        }
        setLiterature(merged);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load data');
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const stage = investigation
    ? deriveStage(investigation, notes, rawMaterials.components, rawMaterials.concepts)
    : 'discovery';

  const stageCounts: StageCounts = {
    discovery: { systems: systems.length, artifacts: rawMaterials.artifacts },
    analysis: { components: rawMaterials.components, concepts: rawMaterials.concepts },
    synthesis: {
      archNotes: notes.filter((n) => n.type === 'architecture').length,
      assessNotes: notes.filter((n) => n.type === 'assessment').length,
    },
    done: { complete: investigation?.status === 'complete' },
  };

  const keyFindings = notes.filter((n) => n.type && SYNTHESIS_NOTE_TYPES.has(n.type));

  return {
    loading,
    error,
    investigation,
    systems,
    stage,
    stageCounts,
    keyFindings,
    literature,
    rawMaterials,
    refresh: fetchData,
  };
}
