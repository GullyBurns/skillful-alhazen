import { NextRequest, NextResponse } from 'next/server';
import { showOperation } from '@/lib/bioskills-index';

export async function GET(
  _req: NextRequest,
  { params }: { params: Promise<{ eid: string }> }
) {
  try {
    const { eid } = await params;
    const data = await showOperation(eid);
    return NextResponse.json(data);
  } catch (error) {
    console.error('show-operation error:', error);
    return NextResponse.json({ error: 'Failed to fetch EDAM term' }, { status: 500 });
  }
}
