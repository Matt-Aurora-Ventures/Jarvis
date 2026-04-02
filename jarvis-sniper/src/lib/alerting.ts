/**
 * Alerting Module for Risk Worker and Sniper Operations
 *
 * Purpose: Send notifications when trades execute, triggers fire, or anomalies occur.
 * Supports webhooks (Slack, Discord, Telegram, custom).
 */

export interface AlertPayload {
  type: 'entry' | 'exit' | 'sl_hit' | 'tp_hit' | 'trail_stop' | 'error' | 'warning';
  mint: string;
  symbol?: string;
  amount?: number;
  pnlPercent?: number;
  pnlSol?: number;
  trigger?: string;
  txHash?: string;
  message: string;
  timestamp: number;
}

export interface AlertConfig {
  webhookUrl?: string;
  telegramBotToken?: string;
  telegramChatId?: string;
  enabled: boolean;
  minPnlForAlert?: number; // Only alert if |pnl| > this threshold
}

const DEFAULT_CONFIG: AlertConfig = {
  webhookUrl: process.env.ALERT_WEBHOOK_URL,
  telegramBotToken: process.env.TELEGRAM_BOT_TOKEN,
  telegramChatId: process.env.TELEGRAM_CHAT_ID,
  enabled: !!(process.env.ALERT_WEBHOOK_URL || process.env.TELEGRAM_BOT_TOKEN),
  minPnlForAlert: 0,
};

/**
 * Send an alert to configured channels.
 */
export async function sendAlert(payload: AlertPayload, config = DEFAULT_CONFIG): Promise<boolean> {
  if (!config.enabled) return false;

  // Filter by PnL threshold
  if (config.minPnlForAlert && payload.pnlPercent !== undefined) {
    if (Math.abs(payload.pnlPercent) < config.minPnlForAlert) {
      return false;
    }
  }

  const promises: Promise<boolean>[] = [];

  // Webhook (generic JSON POST)
  if (config.webhookUrl) {
    promises.push(sendWebhook(config.webhookUrl, payload));
  }

  // Telegram
  if (config.telegramBotToken && config.telegramChatId) {
    promises.push(sendTelegram(config.telegramBotToken, config.telegramChatId, payload));
  }

  const results = await Promise.allSettled(promises);
  return results.some(r => r.status === 'fulfilled' && r.value === true);
}

async function sendWebhook(url: string, payload: AlertPayload): Promise<boolean> {
  try {
    const res = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
      signal: AbortSignal.timeout(5000),
    });
    return res.ok;
  } catch {
    return false;
  }
}

async function sendTelegram(botToken: string, chatId: string, payload: AlertPayload): Promise<boolean> {
  try {
    const emoji = {
      entry: '🟢',
      exit: '🔴',
      sl_hit: '🛑',
      tp_hit: '🎯',
      trail_stop: '📈',
      error: '❌',
      warning: '⚠️',
    }[payload.type] || '📢';

    const lines = [
      `${emoji} *${payload.type.toUpperCase().replace('_', ' ')}*`,
      `Token: ${payload.symbol || payload.mint.slice(0, 8)}`,
    ];

    if (payload.pnlPercent !== undefined) {
      const sign = payload.pnlPercent >= 0 ? '+' : '';
      lines.push(`PnL: ${sign}${payload.pnlPercent.toFixed(2)}%`);
    }

    if (payload.amount !== undefined) {
      lines.push(`Amount: ${payload.amount.toFixed(4)} SOL`);
    }

    if (payload.txHash) {
      lines.push(`[TX](https://solscan.io/tx/${payload.txHash})`);
    }

    lines.push(`\n${payload.message}`);

    const url = `https://api.telegram.org/bot${botToken}/sendMessage`;
    const res = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        chat_id: chatId,
        text: lines.join('\n'),
        parse_mode: 'Markdown',
        disable_web_page_preview: true,
      }),
      signal: AbortSignal.timeout(5000),
    });

    return res.ok;
  } catch {
    return false;
  }
}

/**
 * Create an alert for a trade exit.
 */
export function createExitAlert(
  type: 'sl_hit' | 'tp_hit' | 'trail_stop',
  mint: string,
  symbol: string,
  pnlPercent: number,
  pnlSol: number,
  txHash: string,
): AlertPayload {
  return {
    type,
    mint,
    symbol,
    pnlPercent,
    pnlSol,
    txHash,
    message: `${type === 'sl_hit' ? 'Stop Loss' : type === 'tp_hit' ? 'Take Profit' : 'Trailing Stop'} triggered for ${symbol}`,
    timestamp: Date.now(),
  };
}

/**
 * Create an alert for an error or warning.
 */
export function createErrorAlert(
  type: 'error' | 'warning',
  message: string,
  context?: { mint?: string; symbol?: string; txHash?: string },
): AlertPayload {
  return {
    type,
    mint: context?.mint || '',
    symbol: context?.symbol,
    message,
    txHash: context?.txHash,
    timestamp: Date.now(),
  };
}
