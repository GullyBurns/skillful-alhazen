import { NextRequest, NextResponse } from 'next/server';
import { listSkills } from '@/lib/bioskills-index';

export async function GET(
  _req: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  try {
    const { id } = await params;
    const data = await listSkills(id, { limit: 500 }) as { skills: unknown[] };
    // Filter to skills with UMAP coords
    const skills = (data.skills || []).filter(
      (s: unknown) => (s as Record<string, unknown>).umap_x != null && (s as Record<string, unknown>).umap_y != null
    );
    return NextResponse.json({ success: true, skills }, {
      headers: { 'Cache-Control': 's-maxage=300, stale-while-revalidate' },
    });
  } catch (error) {
    console.error('umap-data error:', error);
    return NextResponse.json({ error: 'Failed to fetch UMAP data' }, { status: 500 });
  }
}
