import axios from 'axios';
import { EventEmitter } from 'events';
import { config } from '../config/index.js';
import { createModuleLogger } from '../utils/logger.js';
import type { TwitterSignalEvent } from '../types/index.js';

const log = createModuleLogger('twitter-listener');

// Regex to detect Solana contract addresses in tweets
const SOL_ADDRESS_REGEX = /[1-9A-HJ-NP-Za-km-z]{32,44}/g;

// Known crypto influencer accounts to monitor
const INFLUENCER_IDS = [
  // Add actual Twitter user IDs here
];

interface Tweet {
  id: string;
  text: string;
  author_id: string;
  created_at: string;
}

export class TwitterListener extends EventEmitter {
  private pollInterval: ReturnType<typeof setInterval> | null = null;
  private lastCheckedId: string | null = null;
  private isRunning: boolean = false;

  async start(): Promise<void> {
    if (!config.twitterBearerToken) {
      log.warn('Twitter bearer token not set, using polling fallback via DexScreener');
      this.startDexScreenerFallback();
      return;
    }

    this.isRunning = true;
    log.info('Starting Twitter listener (polling mode)');

    // Poll every 30 seconds (within free tier limits)
    this.pollInterval = setInterval(() => this.pollTweets(), 30_000);
    await this.pollTweets();
  }

  private async pollTweets(): Promise<void> {
    if (!this.isRunning) return;

    try {
      // Search recent tweets about new Solana tokens
      const query = encodeURIComponent(
        '(new token OR just launched OR stealth launch OR pump.fun) solana -is:retweet -is:reply lang:en'
      );

      const url = `https://api.twitter.com/2/tweets/search/recent?query=${query}&max_results=10&tweet.fields=created_at,author_id&sort_order=recency`;

      const resp = await axios.get<{ data?: Tweet[] }>(url, {
        headers: { Authorization: `Bearer ${config.twitterBearerToken}` },
        timeout: 10000,
      });

      const tweets = resp.data.data ?? [];

      for (const tweet of tweets) {
        if (this.lastCheckedId && tweet.id <= this.lastCheckedId) continue;

        // Extract Solana addresses from tweet
        const addresses = tweet.text.match(SOL_ADDRESS_REGEX) ?? [];
        const validAddresses = addresses.filter(a => a.length >= 32 && a.length <= 44);

        if (validAddresses.length > 0) {
          for (const addr of validAddresses) {
            const sentiment = this.quickSentiment(tweet.text);

            const event: TwitterSignalEvent = {
              type: 'twitter_signal',
              mint: addr,
              symbol: null,
              tweetId: tweet.id,
              author: tweet.author_id,
              text: tweet.text,
              sentiment,
              timestamp: new Date(tweet.created_at).getTime(),
            };

            log.info('Twitter signal detected', {
              mint: addr.slice(0, 8),
              sentiment: sentiment.toFixed(2),
              author: tweet.author_id,
            });

            this.emit('signal', event);
          }
        }
      }

      if (tweets.length > 0) {
        this.lastCheckedId = tweets[0].id;
      }
    } catch (err) {
      const errMsg = (err as Error).message;
      if (errMsg.includes('429')) {
        log.warn('Twitter rate limited, backing off');
      } else {
        log.error('Twitter poll failed', { error: errMsg });
      }
    }
  }

  private startDexScreenerFallback(): void {
    this.isRunning = true;
    log.info('Starting DexScreener trending tokens fallback');

    // Poll DexScreener for trending tokens as a Twitter alternative
    this.pollInterval = setInterval(() => this.pollDexScreener(), 60_000);
    this.pollDexScreener();
  }

  private async pollDexScreener(): Promise<void> {
    try {
      const resp = await axios.get<{ pairs?: Array<{ baseToken: { address: string; symbol: string }; priceChange: { h1: number } }> }>(
        'https://api.dexscreener.com/latest/dex/tokens/trending',
        { timeout: 5000 }
      );

      const pairs = resp.data.pairs ?? [];
      for (const pair of pairs.slice(0, 5)) {
        if (pair.priceChange?.h1 > 50) { // >50% in 1 hour
          const event: TwitterSignalEvent = {
            type: 'twitter_signal',
            mint: pair.baseToken.address,
            symbol: pair.baseToken.symbol,
            tweetId: '',
            author: 'dexscreener',
            text: `Trending: ${pair.baseToken.symbol} +${pair.priceChange.h1.toFixed(0)}% 1h`,
            sentiment: 0.7,
            timestamp: Date.now(),
          };

          this.emit('signal', event);
        }
      }
    } catch (err) {
      log.error('DexScreener poll failed', { error: (err as Error).message });
    }
  }

  private quickSentiment(text: string): number {
    const lower = text.toLowerCase();
    let score = 0;

    // Bullish signals
    const bullish = ['moon', 'gem', 'bullish', 'buy', '100x', 'lfg', 'launch', 'next', 'early', 'alpha', 'based'];
    const bearish = ['rug', 'scam', 'dump', 'sell', 'avoid', 'warning', 'fake', 'honeypot'];

    for (const word of bullish) {
      if (lower.includes(word)) score += 0.15;
    }
    for (const word of bearish) {
      if (lower.includes(word)) score -= 0.25;
    }

    return Math.max(-1, Math.min(1, score));
  }

  async stop(): Promise<void> {
    this.isRunning = false;
    if (this.pollInterval) {
      clearInterval(this.pollInterval);
      this.pollInterval = null;
    }
    log.info('Twitter listener stopped');
  }
}
