'use client';

import { ZoomIn, ZoomOut, Maximize2 } from 'lucide-react';
import { Button } from '@/components/ui/button';

interface GraphControlsProps {
  onZoomIn?: () => void;
  onZoomOut?: () => void;
  onFitToView?: () => void;
}

export default function GraphControls({
  onZoomIn,
  onZoomOut,
  onFitToView,
}: GraphControlsProps) {
  return (
    <div className="flex flex-col bg-zinc-800 rounded-lg p-1 gap-1">
      <Button
        variant="ghost"
        size="sm"
        onClick={onZoomIn}
        className="h-8 w-8 p-0 text-zinc-400 hover:text-zinc-100 hover:bg-zinc-700"
        title="Zoom in"
      >
        <ZoomIn className="w-4 h-4" />
      </Button>
      <Button
        variant="ghost"
        size="sm"
        onClick={onZoomOut}
        className="h-8 w-8 p-0 text-zinc-400 hover:text-zinc-100 hover:bg-zinc-700"
        title="Zoom out"
      >
        <ZoomOut className="w-4 h-4" />
      </Button>
      <Button
        variant="ghost"
        size="sm"
        onClick={onFitToView}
        className="h-8 w-8 p-0 text-zinc-400 hover:text-zinc-100 hover:bg-zinc-700"
        title="Fit to view"
      >
        <Maximize2 className="w-4 h-4" />
      </Button>
    </div>
  );
}
