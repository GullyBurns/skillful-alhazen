import { readFile } from 'fs/promises';
import path from 'path';
import { getArtifact } from '@/lib/tech-recon';

const CACHE_DIR = path.join(process.env.HOME || '/root', '.alhazen', 'cache');

const CONTENT_TYPES: Record<string, string> = {
  html: 'text/html; charset=utf-8',
  pdf: 'application/pdf',
  json: 'application/json; charset=utf-8',
  text: 'text/plain; charset=utf-8',
  markdown: 'text/plain; charset=utf-8',
  md: 'text/plain; charset=utf-8',
};

export async function GET(
  _req: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params;

  let artifact: { format?: string; cache_path?: string; content?: string };
  try {
    const data = await getArtifact(id);
    artifact = data.artifact as typeof artifact;
  } catch (e) {
    return new Response(`Failed to load artifact metadata: ${e}`, { status: 500 });
  }

  const format = (artifact.format || 'text').toLowerCase();

  // Directory / repo-clone — nothing to serve as a single file
  if (format === 'directory') {
    return new Response('Repository clone — no single file to display.', {
      headers: { 'Content-Type': 'text/plain' },
    });
  }

  // Cached file — read directly from the mounted filesystem
  if (artifact.cache_path) {
    const filePath = path.join(CACHE_DIR, artifact.cache_path);
    try {
      const bytes = await readFile(filePath);
      const contentType = CONTENT_TYPES[format] || 'application/octet-stream';
      return new Response(bytes, { headers: { 'Content-Type': contentType } });
    } catch {
      return new Response(`Cache file not found: ${artifact.cache_path}`, {
        status: 404,
        headers: { 'Content-Type': 'text/plain' },
      });
    }
  }

  // Inline content stored in TypeDB
  if (artifact.content) {
    return new Response(artifact.content, {
      headers: { 'Content-Type': CONTENT_TYPES[format] || 'text/plain; charset=utf-8' },
    });
  }

  return new Response('No content available for this artifact.', {
    status: 404,
    headers: { 'Content-Type': 'text/plain' },
  });
}
