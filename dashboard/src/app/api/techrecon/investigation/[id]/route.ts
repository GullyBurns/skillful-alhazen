import { NextResponse } from 'next/server';
import { getInvestigation } from '@/lib/techrecon';

export async function GET(
  _request: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params;

  try {
    const data = await getInvestigation(id);
    return NextResponse.json(data);
  } catch (error) {
    console.error('Investigation error:', error);
    return NextResponse.json(
      { error: 'Failed to fetch investigation' },
      { status: 500 }
    );
  }
}
