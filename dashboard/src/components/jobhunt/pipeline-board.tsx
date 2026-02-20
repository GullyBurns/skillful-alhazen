'use client';

import Link from 'next/link';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { Button } from '@/components/ui/button';
import { MoreVertical, ExternalLink, MapPin, Building2, DollarSign, Eye } from 'lucide-react';

interface Position {
  id: string;
  title: string;
  short_name: string | null;
  company: string;
  url: string;
  location: string;
  remote_policy: string;
  salary: string;
  priority: string;
  status: string;
}

interface PipelineBoardProps {
  positions: Position[];
  onStatusChange: (positionId: string, newStatus: string) => void;
}

const STATUS_ORDER = [
  'researching',
  'applied',
  'phone-screen',
  'interviewing',
  'offer',
  'rejected',
];

const STATUS_COLORS: Record<string, string> = {
  researching: 'bg-slate-100 text-slate-800',
  applied: 'bg-blue-100 text-blue-800',
  'phone-screen': 'bg-purple-100 text-purple-800',
  interviewing: 'bg-amber-100 text-amber-800',
  offer: 'bg-green-100 text-green-800',
  rejected: 'bg-red-100 text-red-800',
  withdrawn: 'bg-gray-100 text-gray-800',
};

const PRIORITY_COLORS: Record<string, string> = {
  high: 'bg-red-500',
  medium: 'bg-yellow-500',
  low: 'bg-green-500',
};

function PositionCard({
  position,
  onStatusChange,
}: {
  position: Position;
  onStatusChange: (positionId: string, newStatus: string) => void;
}) {
  return (
    <Card className="mb-1.5 hover:shadow-sm transition-shadow group">
      <CardContent className="p-2">
        <div className="flex items-center justify-between gap-1">
          <Link href={`/jobhunt/position/${position.id}`} className="flex-1 min-w-0 cursor-pointer">
            <div className="flex items-center gap-1.5">
              {position.priority === 'high' && (
                <div
                  className={`w-1.5 h-1.5 rounded-full flex-shrink-0 ${PRIORITY_COLORS[position.priority]}`}
                  title={`${position.priority} priority`}
                />
              )}
              <span className="text-xs font-medium group-hover:text-primary transition-colors truncate" title={position.title}>
                {position.short_name || position.title}
              </span>
            </div>
          </Link>

          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="ghost" size="icon" className="h-5 w-5 flex-shrink-0">
                <MoreVertical className="h-3 w-3" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              <DropdownMenuItem asChild>
                <Link href={`/jobhunt/position/${position.id}`}>
                  <Eye className="w-4 h-4 mr-2" />
                  View Details
                </Link>
              </DropdownMenuItem>
              {position.url && (
                <DropdownMenuItem asChild>
                  <a href={position.url} target="_blank" rel="noopener noreferrer">
                    <ExternalLink className="w-4 h-4 mr-2" />
                    View Posting
                  </a>
                </DropdownMenuItem>
              )}
              <DropdownMenuItem
                onClick={() => onStatusChange(position.id, 'applied')}
              >
                Mark as Applied
              </DropdownMenuItem>
              <DropdownMenuItem
                onClick={() => onStatusChange(position.id, 'phone-screen')}
              >
                Phone Screen
              </DropdownMenuItem>
              <DropdownMenuItem
                onClick={() => onStatusChange(position.id, 'interviewing')}
              >
                Interviewing
              </DropdownMenuItem>
              <DropdownMenuItem
                onClick={() => onStatusChange(position.id, 'offer')}
              >
                Received Offer
              </DropdownMenuItem>
              <DropdownMenuItem
                onClick={() => onStatusChange(position.id, 'rejected')}
                className="text-red-600"
              >
                Rejected
              </DropdownMenuItem>
              <DropdownMenuItem
                onClick={() => onStatusChange(position.id, 'withdrawn')}
              >
                Withdraw
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </CardContent>
    </Card>
  );
}

export function PipelineBoard({ positions, onStatusChange }: PipelineBoardProps) {
  // Group positions by status
  const grouped = STATUS_ORDER.reduce((acc, status) => {
    acc[status] = positions.filter((p) => p.status === status);
    return acc;
  }, {} as Record<string, Position[]>);

  return (
    <div className="grid grid-cols-1 md:grid-cols-3 lg:grid-cols-6 gap-4">
      {STATUS_ORDER.map((status) => (
        <div key={status} className="min-w-0">
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-sm font-medium flex items-center justify-between">
                <span className="capitalize">{status.replace('-', ' ')}</span>
                <Badge
                  variant="secondary"
                  className={STATUS_COLORS[status]}
                >
                  {grouped[status]?.length || 0}
                </Badge>
              </CardTitle>
            </CardHeader>
            <CardContent className="pt-0">
              {grouped[status]?.length > 0 ? (
                grouped[status].map((position) => (
                  <PositionCard
                    key={position.id}
                    position={position}
                    onStatusChange={onStatusChange}
                  />
                ))
              ) : (
                <p className="text-xs text-muted-foreground text-center py-4">
                  No positions
                </p>
              )}
            </CardContent>
          </Card>
        </div>
      ))}
    </div>
  );
}
