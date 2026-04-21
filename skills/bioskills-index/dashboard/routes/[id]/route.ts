import { NextRequest, NextResponse } from 'next/server';
import { showIndex } from '@/lib/bioskills-index';

export async function GET(
  _req: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  try {
    const { id } = await params;
    const data = await showIndex(id);
    return NextResponse.json(data);
  } catch (error) {
    console.error('show-index error:', error);
    return NextResponse.json({ error: 'Failed to fetch index' }, { status: 500 });
  }
}
