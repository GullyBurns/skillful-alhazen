import { NextResponse } from 'next/server';
import { getSystem } from '@/lib/techrecon';

export async function GET(
  _request: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params;

  try {
    const data = await getSystem(id);
    return NextResponse.json(data);
  } catch (error) {
    console.error('System error:', error);
    return NextResponse.json(
      { error: 'Failed to fetch system' },
      { status: 500 }
    );
  }
}
