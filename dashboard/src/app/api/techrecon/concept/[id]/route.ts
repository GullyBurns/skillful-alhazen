import { NextResponse } from 'next/server';
import { getConcept } from '@/lib/techrecon';

export async function GET(
  _request: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params;

  try {
    const data = await getConcept(id);
    return NextResponse.json(data);
  } catch (error) {
    console.error('Concept error:', error);
    return NextResponse.json(
      { error: 'Failed to fetch concept' },
      { status: 500 }
    );
  }
}
