'use client';

import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { colors } from './tokens';

interface MarkdownContentProps {
  children: string;
  fontSize?: number;
  color?: string;
}

export default function MarkdownContent({
  children,
  fontSize = 13,
  color = colors.fgDim,
}: MarkdownContentProps) {
  return (
    <ReactMarkdown
      remarkPlugins={[remarkGfm]}
      components={{
        p: ({ children: c }) => (
          <p style={{ margin: '0 0 8px', lineHeight: 1.55, fontSize, color }}>{c}</p>
        ),
        strong: ({ children: c }) => (
          <strong style={{ color: colors.fg, fontWeight: 600 }}>{c}</strong>
        ),
        em: ({ children: c }) => (
          <em style={{ fontStyle: 'italic' }}>{c}</em>
        ),
        a: ({ href, children: c }) => (
          <a
            href={href}
            target="_blank"
            rel="noopener noreferrer"
            style={{
              color: colors.teal,
              textDecoration: 'underline',
              textUnderlineOffset: 2,
            }}
          >
            {c}
          </a>
        ),
        ul: ({ children: c }) => (
          <ul style={{ margin: '4px 0 8px', paddingLeft: 20, fontSize, color }}>{c}</ul>
        ),
        ol: ({ children: c }) => (
          <ol style={{ margin: '4px 0 8px', paddingLeft: 20, fontSize, color }}>{c}</ol>
        ),
        li: ({ children: c }) => (
          <li style={{ marginBottom: 3, lineHeight: 1.5 }}>{c}</li>
        ),
        h1: ({ children: c }) => (
          <h1
            style={{
              fontSize: 18,
              fontWeight: 600,
              color: colors.fg,
              margin: '12px 0 6px',
              fontFamily: 'var(--font-dm-serif), "DM Serif Display", serif',
            }}
          >
            {c}
          </h1>
        ),
        h2: ({ children: c }) => (
          <h2
            style={{
              fontSize: 15,
              fontWeight: 600,
              color: colors.fg,
              margin: '10px 0 4px',
              fontFamily: 'var(--font-dm-serif), "DM Serif Display", serif',
            }}
          >
            {c}
          </h2>
        ),
        h3: ({ children: c }) => (
          <h3 style={{ fontSize: 13, fontWeight: 600, color: colors.fg, margin: '8px 0 4px' }}>
            {c}
          </h3>
        ),
        code: ({ children: c, className }) => {
          const isBlock = className?.includes('language-');
          if (isBlock) {
            return (
              <code
                style={{
                  display: 'block',
                  background: colors.bgSunken,
                  border: `1px solid ${colors.borderDim}`,
                  borderRadius: 3,
                  padding: '8px 12px',
                  fontFamily: 'var(--font-jetbrains-mono), "JetBrains Mono", monospace',
                  fontSize: 11.5,
                  color: colors.fgDim,
                  overflowX: 'auto',
                  margin: '6px 0',
                  whiteSpace: 'pre',
                }}
              >
                {c}
              </code>
            );
          }
          return (
            <code
              style={{
                background: colors.bgSunken,
                border: `1px solid ${colors.borderDim}`,
                borderRadius: 2,
                padding: '1px 5px',
                fontFamily: 'var(--font-jetbrains-mono), "JetBrains Mono", monospace',
                fontSize: '0.9em',
                color: colors.fgDim,
              }}
            >
              {c}
            </code>
          );
        },
        pre: ({ children: c }) => (
          <pre style={{ margin: '6px 0', overflow: 'auto' }}>{c}</pre>
        ),
        blockquote: ({ children: c }) => (
          <blockquote
            style={{
              borderLeft: `3px solid ${colors.border}`,
              paddingLeft: 12,
              margin: '6px 0',
              color: colors.fgFaint,
              fontStyle: 'italic',
            }}
          >
            {c}
          </blockquote>
        ),
        table: ({ children: c }) => (
          <table
            style={{
              borderCollapse: 'collapse',
              width: '100%',
              margin: '8px 0',
              fontSize: 12,
            }}
          >
            {c}
          </table>
        ),
        th: ({ children: c }) => (
          <th
            style={{
              borderBottom: `1px solid ${colors.borderDim}`,
              padding: '4px 8px',
              textAlign: 'left',
              fontFamily: 'var(--font-jetbrains-mono), "JetBrains Mono", monospace',
              fontSize: 10,
              color: colors.fgFaint,
              textTransform: 'uppercase',
              letterSpacing: '0.5px',
            }}
          >
            {c}
          </th>
        ),
        td: ({ children: c }) => (
          <td
            style={{
              borderBottom: `1px solid ${colors.borderDim}`,
              padding: '4px 8px',
              color: colors.fgDim,
            }}
          >
            {c}
          </td>
        ),
        hr: () => (
          <hr style={{ border: 'none', borderTop: `1px solid ${colors.borderDim}`, margin: '12px 0' }} />
        ),
      }}
    >
      {children}
    </ReactMarkdown>
  );
}
