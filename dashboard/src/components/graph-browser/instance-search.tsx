'use client';

import { useState, useCallback } from 'react';
import { Search, Loader2 } from 'lucide-react';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import {
  Table,
  TableHeader,
  TableRow,
  TableHead,
  TableBody,
  TableCell,
} from '@/components/ui/table';
import { Badge } from '@/components/ui/badge';

interface SearchRow {
  id: string;
  name: string;
  type?: string;
  collection?: string;
  score?: number;
}

interface InstanceSearchProps {
  selectedType?: string;
  onEntitySelect?: (entityId: string) => void;
}

export default function InstanceSearch({
  selectedType,
  onEntitySelect,
}: InstanceSearchProps) {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<SearchRow[]>([]);
  const [loading, setLoading] = useState(false);
  const [searched, setSearched] = useState(false);

  const doSearch = useCallback(async () => {
    const q = query.trim();
    if (!q) return;

    setLoading(true);
    setSearched(true);

    try {
      let rows: SearchRow[] = [];

      if (selectedType) {
        // TypeQL query filtered by type
        const safeQuery = q.replace(/'/g, "\\'");
        const typeql = `match $e isa ${selectedType}, has name $n; $n contains '${safeQuery}'; fetch { "id": $e.id, "name": $n };`;
        const res = await fetch('/api/agentic-memory/query', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ typeql, limit: 20 }),
        });
        const data = await res.json();
        if (data.success && data.results) {
          rows = (data.results as Array<Record<string, string>>).map((r) => ({
            id: r.id,
            name: r.name ?? r.id,
            type: selectedType,
          }));
        }
      } else {
        // Semantic search across all collections
        const res = await fetch(
          `/api/agentic-memory/search?query=${encodeURIComponent(q)}&limit=20`,
        );
        const data = await res.json();
        if (data.success && data.results) {
          rows = (
            data.results as Array<{
              payload: Record<string, unknown>;
              collection: string;
              score: number;
            }>
          ).map((r) => ({
            id: String(r.payload?.id ?? r.payload?.entity_id ?? ''),
            name: String(r.payload?.name ?? r.payload?.title ?? r.payload?.id ?? ''),
            collection: r.collection,
            score: r.score,
          }));
        }
      }

      setResults(rows);
    } catch (err) {
      console.error('Search failed:', err);
      setResults([]);
    } finally {
      setLoading(false);
    }
  }, [query, selectedType]);

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') doSearch();
  };

  return (
    <div className="flex flex-col h-full">
      {/* Search bar */}
      <div className="flex items-center gap-2 px-4 py-3 border-b border-zinc-800">
        <div className="relative flex-1">
          <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 w-4 h-4 text-zinc-500" />
          <Input
            placeholder={
              selectedType
                ? `Search ${selectedType} by name...`
                : 'Semantic search across all entities...'
            }
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={handleKeyDown}
            className="pl-9 bg-zinc-900 border-zinc-800"
          />
        </div>
        <Button
          size="sm"
          onClick={doSearch}
          disabled={loading || !query.trim()}
          className="shrink-0"
        >
          {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : 'Search'}
        </Button>
      </div>

      {/* Filter indicator */}
      {selectedType && (
        <div className="px-4 py-1.5 border-b border-zinc-800 bg-zinc-900/50">
          <span className="text-xs text-zinc-500">Filtered to type: </span>
          <Badge variant="secondary" className="text-xs">
            {selectedType}
          </Badge>
        </div>
      )}

      {/* Results */}
      <div className="flex-1 overflow-y-auto">
        {loading && (
          <div className="flex items-center justify-center py-12 text-zinc-500 text-sm">
            <Loader2 className="w-5 h-5 animate-spin mr-2" />
            Searching...
          </div>
        )}

        {!loading && searched && results.length === 0 && (
          <div className="flex items-center justify-center py-12 text-zinc-500 text-sm">
            No results found.
          </div>
        )}

        {!loading && results.length > 0 && (
          <Table>
            <TableHeader>
              <TableRow className="border-zinc-800">
                <TableHead className="text-zinc-400">Name</TableHead>
                <TableHead className="text-zinc-400">
                  {selectedType ? 'Type' : 'Collection'}
                </TableHead>
                <TableHead className="text-zinc-400 font-mono text-xs">
                  ID
                </TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {results.map((row) => (
                <TableRow
                  key={row.id}
                  className="border-zinc-800 cursor-pointer hover:bg-zinc-800/50 transition-colors"
                  onClick={() => onEntitySelect?.(row.id)}
                >
                  <TableCell className="text-zinc-200 text-sm">
                    {row.name}
                  </TableCell>
                  <TableCell>
                    <Badge variant="outline" className="text-xs text-zinc-400 border-zinc-700">
                      {row.type || row.collection || '--'}
                    </Badge>
                  </TableCell>
                  <TableCell className="font-mono text-xs text-zinc-500 max-w-[200px] truncate">
                    {row.id}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}

        {!loading && !searched && (
          <div className="flex flex-col items-center justify-center py-12 text-zinc-500 text-sm">
            <Search className="w-8 h-8 mb-3 text-zinc-700" />
            <p>
              {selectedType
                ? `Search for ${selectedType} entities by name`
                : 'Search across all entities using semantic search'}
            </p>
          </div>
        )}
      </div>
    </div>
  );
}
