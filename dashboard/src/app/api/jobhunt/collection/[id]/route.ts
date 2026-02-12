import { NextRequest, NextResponse } from 'next/server';
import { getCollection } from '@/lib/jobhunt';

export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params;

  try {
    const data = await getCollection(id);
    if (!data) {
      return NextResponse.json(
        { error: 'Collection not found' },
        { status: 404 }
      );
    }
    return NextResponse.json(data);
  } catch (error) {
    console.error('Collection fetch error:', error);
    return NextResponse.json(
      { error: 'Failed to fetch collection' },
      { status: 500 }
    );
  }
}
