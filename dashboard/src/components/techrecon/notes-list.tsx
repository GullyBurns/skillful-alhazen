'use client';

import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Separator } from '@/components/ui/separator';
import { StickyNote } from 'lucide-react';
import { TypeBadge } from './badges';

interface Note {
  id: string;
  name: string;
  content: string;
  type?: string;
  created_at?: string;
}

interface NotesListProps {
  notes: Note[];
  grouped?: boolean;
}

export function NotesList({ notes, grouped = true }: NotesListProps) {
  if (notes.length === 0) {
    return (
      <p className="text-sm text-muted-foreground py-2">No notes available.</p>
    );
  }

  if (!grouped) {
    return (
      <div className="space-y-4">
        {notes.map((note, idx) => (
          <NoteCard key={note.id || idx} note={note} showSeparator={idx < notes.length - 1} />
        ))}
      </div>
    );
  }

  // Group notes by type
  const groups = notes.reduce<Record<string, Note[]>>((acc, note) => {
    const type = note.type || 'general';
    if (!acc[type]) acc[type] = [];
    acc[type].push(note);
    return acc;
  }, {});

  return (
    <div className="space-y-4">
      {Object.entries(groups).map(([type, typeNotes]) => (
        <Card key={type}>
          <CardHeader className="pb-3">
            <CardTitle className="text-sm flex items-center gap-2 capitalize">
              <StickyNote className="w-4 h-4" />
              {type.replace(/-/g, ' ')} Notes
              <Badge variant="secondary" className="ml-auto">
                {typeNotes.length}
              </Badge>
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {typeNotes.map((note, idx) => (
              <NoteCard key={note.id || idx} note={note} showSeparator={idx < typeNotes.length - 1} />
            ))}
          </CardContent>
        </Card>
      ))}
    </div>
  );
}

function NoteCard({ note, showSeparator }: { note: Note; showSeparator: boolean }) {
  return (
    <div className="text-sm">
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
      {note.created_at && (
        <p className="text-xs text-muted-foreground mt-1">
          {new Date(note.created_at).toLocaleDateString()}
        </p>
      )}
      {showSeparator && <Separator className="mt-3" />}
    </div>
  );
}
