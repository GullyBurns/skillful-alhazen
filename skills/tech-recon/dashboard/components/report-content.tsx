'use client';

import { useState, useEffect } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

export function ReportContent({ noteId, preview }: { noteId: string; preview?: string }) {
  const [content, setContent] = useState<string>(preview ?? '');

  useEffect(() => {
    fetch(`/api/tech-recon/note/${noteId}`)
      .then((r) => r.json())
      .then((d) => {
        if (d.note?.content) setContent(d.note.content);
      })
      .catch(() => {});
  }, [noteId]);

  return (
    <div className="prose prose-sm dark:prose-invert max-w-none">
      <ReactMarkdown remarkPlugins={[remarkGfm]}>{content}</ReactMarkdown>
    </div>
  );
}
