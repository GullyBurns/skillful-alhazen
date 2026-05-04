'use client';

import { useState, useMemo } from 'react';
import { Search } from 'lucide-react';
import type { SchemaResult } from '@/lib/agentic-memory';
import { schemaToTree, typeToColor } from '@/lib/graph-browser';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';

interface SchemaTreeProps {
  schema: SchemaResult | null;
  onTypeSelect?: (typeName: string) => void;
  selectedType?: string;
}

export default function SchemaTree({
  schema,
  onTypeSelect,
  selectedType,
}: SchemaTreeProps) {
  const [filter, setFilter] = useState('');

  const tree = useMemo(() => {
    if (!schema?.entities) return [];
    return schemaToTree(schema.entities);
  }, [schema]);

  const totalEntityCount = useMemo(
    () => tree.reduce((sum, ns) => sum + (ns.entityCount ?? 0), 0),
    [tree],
  );

  const filteredTree = useMemo(() => {
    if (!filter.trim()) return tree;
    const q = filter.toLowerCase();
    return tree
      .map((ns) => ({
        ...ns,
        children: ns.children?.filter((c) =>
          c.name.toLowerCase().includes(q),
        ),
      }))
      .filter((ns) => ns.children && ns.children.length > 0);
  }, [tree, filter]);

  if (!schema) {
    return (
      <div className="p-4 text-zinc-500 text-sm">Loading schema...</div>
    );
  }

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="px-3 py-3 border-b border-zinc-800">
        <div className="flex items-center justify-between mb-2">
          <h3 className="text-sm font-semibold text-zinc-100">Entity Types</h3>
          <Badge variant="secondary" className="text-xs">
            {totalEntityCount}
          </Badge>
        </div>
        <div className="relative">
          <Search className="absolute left-2 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-zinc-500" />
          <Input
            placeholder="Filter types..."
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
            className="pl-7 h-8 text-xs bg-zinc-900 border-zinc-800"
          />
        </div>
      </div>

      {/* Tree */}
      <div className="flex-1 overflow-y-auto px-1 py-2 text-sm">
        {filteredTree.map((ns) => (
          <details key={ns.name} open className="mb-1">
            <summary className="flex items-center gap-2 px-2 py-1.5 cursor-pointer rounded hover:bg-zinc-800/50 select-none">
              <span
                className="w-2.5 h-2.5 rounded-full shrink-0"
                style={{ backgroundColor: typeToColor(ns.children?.[0]?.name ?? ns.name) }}
              />
              <span className="font-medium text-zinc-300 text-xs uppercase tracking-wide flex-1">
                {ns.name}
              </span>
              {ns.entityCount != null && ns.entityCount > 0 && (
                <span className="text-[10px] text-zinc-500">
                  {ns.entityCount}
                </span>
              )}
            </summary>
            <ul className="ml-4 border-l border-zinc-800">
              {ns.children?.map((leaf) => {
                const isSelected = selectedType === leaf.type;
                return (
                  <li key={leaf.name}>
                    <button
                      onClick={() => onTypeSelect?.(leaf.type ?? leaf.name)}
                      className={`w-full text-left px-3 py-1 text-xs rounded-r flex items-center justify-between transition-colors ${
                        isSelected
                          ? 'bg-zinc-800 text-cyan-400 font-semibold'
                          : 'text-zinc-400 hover:bg-zinc-800/40 hover:text-zinc-200'
                      }`}
                    >
                      <span className="truncate">{leaf.name}</span>
                      {leaf.entityCount != null && leaf.entityCount > 0 && (
                        <Badge
                          variant="secondary"
                          className="ml-2 text-[10px] px-1.5 py-0 h-4 shrink-0"
                        >
                          {leaf.entityCount}
                        </Badge>
                      )}
                    </button>
                  </li>
                );
              })}
            </ul>
          </details>
        ))}
        {filteredTree.length === 0 && (
          <p className="text-xs text-zinc-500 px-3 py-2 italic">
            No types match &quot;{filter}&quot;
          </p>
        )}
      </div>
    </div>
  );
}
