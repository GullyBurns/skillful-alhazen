'use client';

import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

interface ArtifactViewerProps {
  content: string;
  mimeType?: string;
}

export function ArtifactViewer({ content, mimeType }: ArtifactViewerProps) {
  if (!content) {
    return (
      <p className="text-sm text-muted-foreground">No content available.</p>
    );
  }

  if (mimeType === 'text/markdown' || mimeType?.includes('markdown')) {
    return (
      <div className="prose prose-sm max-w-none dark:prose-invert">
        <ReactMarkdown remarkPlugins={[remarkGfm]}>
          {content}
        </ReactMarkdown>
      </div>
    );
  }

  if (mimeType === 'application/json' || mimeType?.includes('json')) {
    let formatted = content;
    try {
      formatted = JSON.stringify(JSON.parse(content), null, 2);
    } catch {
      // Already formatted or invalid JSON, show as-is
    }
    return (
      <pre className="text-sm bg-muted p-4 rounded-lg overflow-auto max-h-[600px] font-mono">
        {formatted}
      </pre>
    );
  }

  // Default: preformatted text
  return (
    <pre className="text-sm bg-muted p-4 rounded-lg overflow-auto max-h-[600px] whitespace-pre-wrap font-mono">
      {content}
    </pre>
  );
}
