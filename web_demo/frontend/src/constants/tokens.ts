/**
 * Common Solana Token Addresses
 * Mainnet addresses for popular tokens.
 */

export interface TokenInfo {
  address: string;
  symbol: string;
  name: string;
  decimals: number;
}

export const TOKENS: Record<string, TokenInfo> = {
  SOL: {
    address: 'So11111111111111111111111111111111111111112',
    symbol: 'SOL',
    name: 'Solana',
    decimals: 9
  },
  USDC: {
    address: 'EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v',
    symbol: 'USDC',
    name: 'USD Coin',
    decimals: 6
  },
  USDT: {
    address: 'Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB',
    symbol: 'USDT',
    name: 'Tether',
    decimals: 6
  },
  // Add more tokens as needed
};

export const getTokenBySymbol = (symbol: string): TokenInfo | undefined => {
  return TOKENS[symbol];
};

export const getTokenByAddress = (address: string): TokenInfo | undefined => {
  return Object.values(TOKENS).find(token => token.address === address);
};
