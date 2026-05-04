'use client';

import { useState, useEffect } from 'react';
import { X, Loader2, ExternalLink } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Separator } from '@/components/ui/separator';
import Link from 'next/link';

interface EntityData {
  id: string;
  name?: string;
  description?: string;
  'created-at'?: string;
  [key: string]: unknown;
}

interface EntityDetailPanelProps {
  entityId: string | null;
  onClose?: () => void;
  onNavigate?: (entityId: string) => void;
}

const linkClass =
  'text-cyan-400 font-semibold underline underline-offset-2 hover:text-blue-400 transition-colors';

export default function EntityDetailPanel({
  entityId,
  onClose,
  onNavigate,
}: EntityDetailPanelProps) {
  const [entity, setEntity] = useState<EntityData | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!entityId) {
      setEntity(null);
      return;
    }

    let cancelled = false;
    setLoading(true);
    setError(null);

    fetch(`/api/agentic-memory/entity/${encodeURIComponent(entityId)}`)
      .then((res) => {
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        return res.json();
      })
      .then((data) => {
        if (cancelled) return;
        if (data.success && data.entity) {
          setEntity(data.entity as EntityData);
        } else {
          setError(data.error || 'Entity not found');
        }
      })
      .catch((err) => {
        if (!cancelled) setError(String(err));
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [entityId]);

  if (!entityId) return null;

  // Determine which attributes to display (non-null, non-id)
  const attrs: [string, unknown][] = entity
    ? Object.entries(entity).filter(
        ([k, v]) => v != null && k !== 'id',
      )
    : [];

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-zinc-800">
        <h3 className="text-sm font-semibold text-zinc-100 truncate">
          Entity Detail
        </h3>
        <Button
          variant="ghost"
          size="sm"
          onClick={onClose}
          className="h-7 w-7 p-0 text-zinc-400 hover:text-zinc-100"
        >
          <X className="w-4 h-4" />
        </Button>
      </div>

      {/* Body */}
      <div className="flex-1 overflow-y-auto px-4 py-3">
        {loading && (
          <div className="flex items-center justify-center py-8 text-zinc-500 text-sm">
            <Loader2 className="w-5 h-5 animate-spin mr-2" />
            Loading...
          </div>
        )}

        {error && (
          <div className="text-sm text-red-400 py-4">
            <p className="font-medium">Error</p>
            <p className="text-xs mt-1">{error}</p>
          </div>
        )}

        {entity && !loading && (
          <div className="space-y-4">
            {/* Type badge */}
            {entity.type != null && (
              <Badge variant="secondary" className="text-xs">
                {String(entity.type) as React.ReactNode}
              </Badge>
            )}

            {/* Name */}
            <h4 className="text-lg font-semibold text-zinc-100">
              {entity.name ?? entityId}
            </h4>

            {/* ID */}
            <p className="font-mono text-xs text-zinc-500 break-all">
              {entityId}
            </p>

            <Separator className="bg-zinc-800" />

            {/* Attributes table */}
            {attrs.length > 0 && (
              <div className="space-y-2">
                <h5 className="text-xs font-medium text-zinc-400 uppercase tracking-wide">
                  Attributes
                </h5>
                <dl className="space-y-1.5">
                  {attrs.map(([key, value]) => (
                    <div key={key} className="grid grid-cols-[100px_1fr] gap-2">
                      <dt className="text-xs text-zinc-500 truncate font-mono">
                        {key}
                      </dt>
                      <dd className="text-xs text-zinc-300 break-words">
                        {renderValue(key, value, onNavigate)}
                      </dd>
                    </div>
                  ))}
                </dl>
              </div>
            )}

            <Separator className="bg-zinc-800" />

            {/* Full detail link */}
            <Link
              href={`/agentic-memory/graph-browser/entity/${encodeURIComponent(entityId)}`}
              className={`inline-flex items-center gap-1.5 text-sm ${linkClass}`}
            >
              <ExternalLink className="w-3.5 h-3.5" />
              View full detail
            </Link>
          </div>
        )}
      </div>
    </div>
  );
}

function renderValue(
  _key: string,
  value: unknown,
  onNavigate?: (id: string) => void,
): React.ReactNode {
  if (value == null) return '--';

  // Dates
  if (typeof value === 'string' && /^\d{4}-\d{2}-\d{2}T/.test(value)) {
    return new Date(value).toLocaleString();
  }

  // Numbers
  if (typeof value === 'number') {
    return String(value);
  }

  // Booleans
  if (typeof value === 'boolean') {
    return value ? 'Yes' : 'No';
  }

  // Strings that look like entity IDs (contain hyphens and hex)
  if (
    typeof value === 'string' &&
    /^[a-z]+-[a-f0-9]{8,}/.test(value) &&
    onNavigate
  ) {
    return (
      <button
        onClick={() => onNavigate(value)}
        className="text-cyan-400 font-semibold underline underline-offset-2 hover:text-blue-400 transition-colors text-left"
      >
        {value}
      </button>
    );
  }

  // Long strings: truncate with title
  const s = String(value);
  if (s.length > 200) {
    return (
      <span title={s}>
        {s.slice(0, 200)}...
      </span>
    );
  }

  return s;
}
