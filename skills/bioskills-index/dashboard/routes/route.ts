import { NextResponse } from 'next/server';
import { listIndices } from '@/lib/bioskills-index';

export async function GET() {
  try {
    const data = await listIndices();
    return NextResponse.json(data);
  } catch (error) {
    console.error('bioskills-index list error:', error);
    return NextResponse.json({ error: 'Failed to list indices' }, { status: 500 });
  }
}
