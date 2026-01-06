#!/usr/bin/env python3
"""Show trending low cap tokens with sentiment analysis."""

from core.dexscreener import get_solana_trending
from core import x_sentiment

def show_trending_low_caps():
    # Get trending Solana low caps
    trending_pairs = get_solana_trending(
        min_liquidity=5000,
        max_liquidity=800000,
        min_volume_24h=1000,
        limit=30
    )

    print('🚀 TRENDING LOW CAPS with Grok Sentiment Analysis:')
    print('='*80)

    # Get sentiment for the promising ones
    sentiment_texts = []
    for pair in trending_pairs[:8]:
        if pair.base_token_symbol and pair.base_token_symbol.strip():
            text = f'${pair.base_token_symbol} ({pair.base_token_name}) - Solana memecoin'
            if pair.price_change_24h != 0:
                text += f' {pair.price_change_24h:+.0f}% today'
            sentiment_texts.append(text)
        else:
            sentiment_texts.append('')

    sentiments = x_sentiment.batch_sentiment_analysis(sentiment_texts, focus='trading')

    for i, (pair, sentiment) in enumerate(zip(trending_pairs[:8], sentiments), 1):
        if not pair.base_token_symbol or not pair.base_token_symbol.strip():
            continue
        
        # Sentiment display
        sentiment_emoji = '⚪'
        sentiment_str = 'Not analyzed'
        
        if sentiment:
            sentiment_map = {'positive': '🟢', 'negative': '🔴', 'neutral': '⚪', 'mixed': '🟡'}
            sentiment_emoji = sentiment_map.get(sentiment.sentiment, '⚪')
            sentiment_str = f'{sentiment_emoji} {sentiment.sentiment.upper()} ({sentiment.confidence:.0%})'
        
        # Market cap estimate
        market_cap_est = f'${pair.liquidity_usd * 25 / 1000:.0f}K'
        
        # Volume trend indicator  
        vol_indicator = '📈' if pair.price_change_24h > 10 else '📉' if pair.price_change_24h < -10 else '→'
        
        print(f'{i:2d}. {pair.base_token_symbol:12} | Est.Cap: {market_cap_est:8} | {vol_indicator} {pair.price_change_24h:+.1f}%')
        print(f'    Price: ${pair.price_usd:.8f} | Liq: ${pair.liquidity_usd:,.0f} | Vol: ${pair.volume_24h:,.0f}')
        print(f'    Sentiment: {sentiment_str}')
        
        if sentiment and sentiment.market_relevance:
            print(f'    Market: {sentiment.market_relevance[:60]}...')
            
        if pair.base_token_name and len(pair.base_token_name) > 2:
            print(f'    Name: {pair.base_token_name[:50]}')
        
        print()

    print(f'Total low caps found: {len(trending_pairs)}')

if __name__ == "__main__":
    show_trending_low_caps()