import axios from 'axios';
import { config } from '../config/index.js';
import { XAI_API } from '../config/constants.js';
import { createModuleLogger } from '../utils/logger.js';
import type { SentimentResult } from '../types/index.js';

const log = createModuleLogger('sentiment');

// Sanitize user-controlled strings before injecting into AI prompts
function sanitize(input: string): string {
  return input
    .replace(/[{}[\]]/g, '') // remove JSON-like characters
    .replace(/\n/g, ' ')     // flatten newlines
    .slice(0, 200);           // cap length
}

interface GrokResponse {
  choices: Array<{
    message: { content: string };
  }>;
}

export async function analyzeSentiment(
  mintAddress: string,
  symbol: string,
  context: string = '',
): Promise<SentimentResult> {
  if (!config.xaiApiKey) {
    return {
      mint: mintAddress,
      symbol,
      score: 0,
      confidence: 0,
      source: 'none',
      reasoning: 'No XAI API key configured',
      analyzedAt: Date.now(),
    };
  }

  try {
    const prompt = `Analyze the following Solana memecoin for trading potential. Give a sentiment score from -1.0 (extremely bearish) to +1.0 (extremely bullish), a confidence score from 0 to 1, and brief reasoning.

Token: ${sanitize(symbol)} (${mintAddress})
${context ? `Additional context: ${sanitize(context)}` : ''}

Respond in JSON format only:
{"score": <number>, "confidence": <number>, "reasoning": "<string>"}`;

    const resp = await axios.post<GrokResponse>(
      `${XAI_API}/chat/completions`,
      {
        model: 'grok-3-mini',
        messages: [
          { role: 'system', content: 'You are a crypto market analyst. Be concise and data-driven. Return valid JSON only.' },
          { role: 'user', content: prompt },
        ],
        temperature: 0.3,
        max_tokens: 200,
      },
      {
        headers: {
          Authorization: `Bearer ${config.xaiApiKey}`,
          'Content-Type': 'application/json',
        },
        timeout: 10000,
      }
    );

    const content = resp.data.choices[0]?.message?.content?.trim();
    if (!content) throw new Error('Empty Grok response');

    // Parse JSON from response (handle markdown code blocks)
    const jsonStr = content.replace(/```json\n?/g, '').replace(/```\n?/g, '').trim();
    const parsed = JSON.parse(jsonStr) as { score: number; confidence: number; reasoning: string };

    const result: SentimentResult = {
      mint: mintAddress,
      symbol,
      score: Math.max(-1, Math.min(1, parsed.score)),
      confidence: Math.max(0, Math.min(1, parsed.confidence)),
      source: 'grok',
      reasoning: parsed.reasoning,
      analyzedAt: Date.now(),
    };

    log.info('Sentiment analysis complete', {
      symbol,
      score: result.score.toFixed(2),
      confidence: result.confidence.toFixed(2),
    });

    return result;
  } catch (err) {
    log.error('Sentiment analysis failed', { symbol, error: (err as Error).message });
    return {
      mint: mintAddress,
      symbol,
      score: 0,
      confidence: 0,
      source: 'error',
      reasoning: (err as Error).message,
      analyzedAt: Date.now(),
    };
  }
}

export async function batchSentimentAnalysis(
  tokens: Array<{ mint: string; symbol: string; context?: string }>,
): Promise<SentimentResult[]> {
  // Process in parallel with concurrency limit of 3
  const results: SentimentResult[] = [];
  const batchSize = 3;

  for (let i = 0; i < tokens.length; i += batchSize) {
    const batch = tokens.slice(i, i + batchSize);
    const batchResults = await Promise.all(
      batch.map(t => analyzeSentiment(t.mint, t.symbol, t.context))
    );
    results.push(...batchResults);
  }

  return results;
}
