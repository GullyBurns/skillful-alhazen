import { NextRequest, NextResponse } from 'next/server';
import { getNotes } from '@/lib/jobhunt';

export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params;

  try {
    const data = await getNotes(id);
    return NextResponse.json(data);
  } catch (error) {
    console.error('Notes fetch error:', error);
    return NextResponse.json(
      { error: 'Failed to fetch notes' },
      { status: 500 }
    );
  }
}
