'use client';

import { useState, useEffect } from 'react';
import { MarkdownContent } from './atoms';

export function ReportContent({ noteId, preview }: { noteId: string; preview?: string }) {
  const [content, setContent] = useState<string>(preview ?? '');

  useEffect(() => {
    fetch(`/api/tech-recon/note/${noteId}`)
      .then(r => r.json())
      .then(d => { if (d.note?.content) setContent(d.note.content); })
      .catch(() => {});
  }, [noteId]);

  return <MarkdownContent content={content} />;
}
