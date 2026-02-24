# Architecture

## Design Pattern
Jarvis uses a fully decoupled **Autonomous Mesh / Multi-Agent Architecture**.
There is no single "brain" script that runs everything constantly. Instead, discrete autonomous agents perform specialized tasks.

## Layers & Components
1. **Trading Intelligence Layer**
   - Autonomous execution on Solana.
   - Separate modules for token sniping, scaling positions, stop-loss check algorithms.
2. **Monitoring & Intel Layer**
   - Agents constantly tracking Bags.fm, X/Twitter, and CoinGecko info.
3. **Communication Layer**
   - Telegram bot acting as the central interface for humans.
   - Discord/Twitter bots executing outward flows.
4. **Data & Execution Storage Layer**
   - PostgreSQL semantic memories.
   - Ephemeral file storage / JSON.

## Process Flow
- Processes run independently via `supervisor`, `Docker` compose, or crontab-like watchdogs.
- They communicate via common database state or messaging/webhooks.

## Strengths
- Highly resilient. If one bot fails, others keep trading.
- Easy to update (can swap the API keys or change the Grok prompts).

## Weaknesses
- Data sync synchronization bugs (like Telegram polling conflicts).
- High complexity for new devs when tracking down which component handles which trade signal.
