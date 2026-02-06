import { NextRequest, NextResponse } from 'next/server';

const XAI_API_URL = 'https://api.x.ai/v1/chat/completions';
const XAI_API_KEY = process.env.NEXT_PUBLIC_XAI_API_KEY || '';

export async function POST(req: NextRequest) {
    if (!XAI_API_KEY) {
        return NextResponse.json({ error: 'API key not configured' }, { status: 500 });
    }

    try {
        const body = await req.json();

        const response = await fetch(XAI_API_URL, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${XAI_API_KEY}`,
            },
            body: JSON.stringify(body),
        });

        if (!response.ok) {
            const errText = await response.text().catch(() => '');
            console.error(`Grok API error: ${response.status}`, errText);
            return NextResponse.json(
                { error: `Grok API error: ${response.status}`, details: errText },
                { status: response.status }
            );
        }

        const data = await response.json();
        return NextResponse.json(data);
    } catch (error) {
        console.error('Grok proxy error:', error);
        return NextResponse.json({ error: 'Internal proxy error' }, { status: 500 });
    }
}
