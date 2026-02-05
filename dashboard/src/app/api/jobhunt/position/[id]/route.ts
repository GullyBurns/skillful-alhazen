import { NextRequest, NextResponse } from 'next/server';
import { getPosition } from '@/lib/jobhunt';

export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params;

  try {
    const data = await getPosition(id);
    if (!data) {
      return NextResponse.json(
        { error: 'Position not found' },
        { status: 404 }
      );
    }
    return NextResponse.json(data);
  } catch (error) {
    console.error('Position fetch error:', error);
    return NextResponse.json(
      { error: 'Failed to fetch position' },
      { status: 500 }
    );
  }
}
