/**
 * xStocks + PreStocks + Indexes — Complete Token Registry
 *
 * Contract addresses sourced from backed.fi (xStocks) and prestocks.com (PreStocks).
 * All tokens are SPL tokens on Solana.
 */
// ============================================================================
// xStocks — Backed.fi tokenized equities (1:1 backed by real shares)
// ============================================================================
export const XSTOCKS = [
    // === Tech Mega-Caps ===
    { ticker: 'AAPLx', name: 'Apple', company: 'Apple Inc.', category: 'XSTOCK', sector: 'Technology', mintAddress: 'XsbEhLAtcf6HdfpFZ5xEMdqW8nfAvcsP5bdudRLJzJp', description: 'Consumer electronics, software, and services' },
    { ticker: 'MSFTx', name: 'Microsoft', company: 'Microsoft Corp.', category: 'XSTOCK', sector: 'Technology', mintAddress: 'XspzcW1PRtgf6Wj92HCiZdjzKCyFekVD8P5Ueh3dRMX', description: 'Cloud computing, productivity software, AI' },
    { ticker: 'GOOGLx', name: 'Alphabet', company: 'Alphabet Inc.', category: 'XSTOCK', sector: 'Technology', mintAddress: 'XsCPL9dNWBMvFtTmwcCA5v3xWPSMEBCszbQdiLLq6aN', description: 'Search, cloud, AI, YouTube' },
    { ticker: 'AMZNx', name: 'Amazon', company: 'Amazon.com Inc.', category: 'XSTOCK', sector: 'Technology', mintAddress: 'Xs3eBt7uRfJX8QUs4suhyU8p2M6DoUDrJyWBa8LLZsg', description: 'E-commerce, AWS cloud, logistics' },
    { ticker: 'METAx', name: 'Meta', company: 'Meta Platforms Inc.', category: 'XSTOCK', sector: 'Technology', mintAddress: 'Xsa62P5mvPszXL1krVUnU5ar38bBSVcWAB6fmPCo5Zu', description: 'Social media, VR/AR, AI' },
    { ticker: 'NVDAx', name: 'NVIDIA', company: 'NVIDIA Corp.', category: 'XSTOCK', sector: 'Technology', mintAddress: 'Xsc9qvGR1efVDFGLrVsmkzv3qi45LTBjeUKSPmx9qEh', description: 'GPU computing, AI chips, data center' },
    { ticker: 'AVGOx', name: 'Broadcom', company: 'Broadcom Inc.', category: 'XSTOCK', sector: 'Technology', mintAddress: 'XsgSaSvNSqLTtFuyWPBhK9196Xb9Bbdyjj4fH3cPJGo', description: 'Semiconductors, infrastructure software' },
    { ticker: 'ORCLx', name: 'Oracle', company: 'Oracle Corp.', category: 'XSTOCK', sector: 'Technology', mintAddress: 'XsjFwUPiLofddX5cWFHW35GCbXcSu1BCUGfxoQAQjeL', description: 'Enterprise software, cloud infrastructure' },
    { ticker: 'CRMx', name: 'Salesforce', company: 'Salesforce Inc.', category: 'XSTOCK', sector: 'Technology', mintAddress: 'XsczbcQ3zfcgAEt9qHQES8pxKAVG5rujPSHQEXi4kaN', description: 'CRM software, enterprise cloud' },
    { ticker: 'CSCOx', name: 'Cisco', company: 'Cisco Systems', category: 'XSTOCK', sector: 'Technology', mintAddress: 'Xsr3pdLQyXvDJBFgpR5nexCEZwXvigb8wbPYp4YoNFf', description: 'Networking equipment, cybersecurity' },
    { ticker: 'ACNx', name: 'Accenture', company: 'Accenture plc', category: 'XSTOCK', sector: 'Technology', mintAddress: 'Xs5UJzmCRQ8DWZjskExdSQDnbE6iLkRu2jjrRAB1JSU', description: 'IT consulting, digital transformation' },
    { ticker: 'INTCx', name: 'Intel', company: 'Intel Corp.', category: 'XSTOCK', sector: 'Technology', mintAddress: 'XshPgPdXFRWB8tP1j82rebb2Q9rPgGX37RuqzohmArM', description: 'Semiconductors, processors' },
    { ticker: 'IBMx', name: 'IBM', company: 'IBM Corp.', category: 'XSTOCK', sector: 'Technology', mintAddress: 'XspwhyYPdWVM8XBHZnpS9hgyag9MKjLRyE3tVfmCbSr', description: 'Enterprise IT, hybrid cloud, AI' },
    { ticker: 'MRVLx', name: 'Marvell', company: 'Marvell Technology', category: 'XSTOCK', sector: 'Technology', mintAddress: 'XsuxRGDzbLjnJ72v74b7p9VY6N66uYgTCyfwwRjVCJA', description: 'Semiconductors, data infrastructure' },
    // === Software & Cybersecurity ===
    { ticker: 'CRWDx', name: 'CrowdStrike', company: 'CrowdStrike Holdings', category: 'XSTOCK', sector: 'Cybersecurity', mintAddress: 'Xs7xXqkcK7K8urEqGg52SECi79dRp2cEKKuYjUePYDw', description: 'Endpoint security, cloud workload protection' },
    { ticker: 'PLTRx', name: 'Palantir', company: 'Palantir Technologies', category: 'XSTOCK', sector: 'Technology', mintAddress: 'XsoBhf2ufR8fTyNSjqfU71DYGaE6Z3SUGAidpzriAA4', description: 'Data analytics, AI, government & enterprise' },
    { ticker: 'NFLXx', name: 'Netflix', company: 'Netflix Inc.', category: 'XSTOCK', sector: 'Entertainment', mintAddress: 'XsEH7wWfJJu2ZT3UCFeVfALnVA6CP5ur7Ee11KmzVpL', description: 'Streaming entertainment' },
    { ticker: 'APPx', name: 'AppLovin', company: 'AppLovin Corp.', category: 'XSTOCK', sector: 'Technology', mintAddress: 'XsPdAVBi8Zc1xvv53k4JcMrQaEDTgkGqKYeh7AYgPHV', description: 'Mobile app monetization, AI marketing' },
    // === EV & Auto ===
    { ticker: 'TSLAx', name: 'Tesla', company: 'Tesla Inc.', category: 'XSTOCK', sector: 'Auto & EV', mintAddress: 'XsDoVfqeBukxuZHWhdvWHBhgEHjGNst4MLodqsJHzoB', description: 'Electric vehicles, energy, autonomous driving' },
    { ticker: 'GMEx', name: 'GameStop', company: 'GameStop Corp.', category: 'XSTOCK', sector: 'Retail', mintAddress: 'Xsf9mBktVB9BSU5kf4nHxPq5hCBJ2j2ui3ecFGxPRGc', description: 'Video game retail, meme stock' },
    // === Finance ===
    { ticker: 'JPMx', name: 'JPMorgan', company: 'JPMorgan Chase & Co.', category: 'XSTOCK', sector: 'Finance', mintAddress: 'XsMAqkcKsUewDrzVkait4e5u4y8REgtyS7jWgCpLV2C', description: 'Investment banking, financial services' },
    { ticker: 'GSx', name: 'Goldman Sachs', company: 'Goldman Sachs Group', category: 'XSTOCK', sector: 'Finance', mintAddress: 'XsgaUyp4jd1fNBCxgtTKkW64xnnhQcvgaxzsbAq5ZD1', description: 'Investment banking, asset management' },
    { ticker: 'BACx', name: 'Bank of America', company: 'Bank of America Corp.', category: 'XSTOCK', sector: 'Finance', mintAddress: 'XswsQk4duEQmCbGzfqUUWYmi7pV7xpJ9eEmLHXCaEQP', description: 'Consumer banking, wealth management' },
    { ticker: 'Vx', name: 'Visa', company: 'Visa Inc.', category: 'XSTOCK', sector: 'Finance', mintAddress: 'XsqgsbXwWogGJsNcVZ3TyVouy2MbTkfCFhCGGGcQZ2p', description: 'Payment processing network' },
    { ticker: 'MAx', name: 'Mastercard', company: 'Mastercard Inc.', category: 'XSTOCK', sector: 'Finance', mintAddress: 'XsApJFV9MAktqnAc6jqzsHVujxkGm9xcSUffaBoYLKC', description: 'Payment technology' },
    { ticker: 'COINx', name: 'Coinbase', company: 'Coinbase Global', category: 'XSTOCK', sector: 'Crypto', mintAddress: 'Xs7ZdzSHLU9ftNJsii5fCeJhoRWSC32SQGzGQtePxNu', description: 'Cryptocurrency exchange' },
    { ticker: 'HOODx', name: 'Robinhood', company: 'Robinhood Markets', category: 'XSTOCK', sector: 'Finance', mintAddress: 'XsvNBAYkrDRNhA7wPHQfX3ZUXZyZLdnCQDfHZ56bzpg', description: 'Retail brokerage, crypto trading' },
    { ticker: 'MSTRx', name: 'MicroStrategy', company: 'MicroStrategy Inc.', category: 'XSTOCK', sector: 'Crypto', mintAddress: 'XsP7xzNPvEHS1m6qfanPUGjNmdnmsLKEoNAnHjdxxyZ', description: 'Bitcoin treasury, business analytics' },
    { ticker: 'BRK.Bx', name: 'Berkshire B', company: 'Berkshire Hathaway', category: 'XSTOCK', sector: 'Finance', mintAddress: 'Xs6B6zawENwAbWVi7w92rjazLuAr5Az59qgWKcNb45x', description: 'Warren Buffett conglomerate' },
    // === Healthcare & Pharma ===
    { ticker: 'LLYx', name: 'Eli Lilly', company: 'Eli Lilly & Co.', category: 'XSTOCK', sector: 'Healthcare', mintAddress: 'Xsnuv4omNoHozR6EEW5mXkw8Nrny5rB3jVfLqi6gKMH', description: 'Pharmaceuticals, diabetes, obesity drugs' },
    { ticker: 'UNHx', name: 'UnitedHealth', company: 'UnitedHealth Group', category: 'XSTOCK', sector: 'Healthcare', mintAddress: 'XszvaiXGPwvk2nwb3o9C1CX4K6zH8sez11E6uyup6fe', description: 'Health insurance, Optum services' },
    { ticker: 'JNJx', name: 'J&J', company: 'Johnson & Johnson', category: 'XSTOCK', sector: 'Healthcare', mintAddress: 'XsGVi5eo1Dh2zUpic4qACcjuWGjNv8GCt3dm5XcX6Dn', description: 'Pharmaceuticals, medical devices' },
    { ticker: 'PFEx', name: 'Pfizer', company: 'Pfizer Inc.', category: 'XSTOCK', sector: 'Healthcare', mintAddress: 'XsAtbqkAP1HJxy7hFDeq7ok6yM43DQ9mQ1Rh861X8rw', description: 'Pharmaceuticals, vaccines' },
    { ticker: 'MRKx', name: 'Merck', company: 'Merck & Co.', category: 'XSTOCK', sector: 'Healthcare', mintAddress: 'XsnQnU7AdbRZYe2akqqpibDdXjkieGFfSkbkjX1Sd1X', description: 'Pharmaceuticals, oncology' },
    { ticker: 'ABBVx', name: 'AbbVie', company: 'AbbVie Inc.', category: 'XSTOCK', sector: 'Healthcare', mintAddress: 'XswbinNKyPmzTa5CskMbCPvMW6G5CMnZXZEeQSSQoie', description: 'Biopharmaceuticals, immunology' },
    { ticker: 'ABTx', name: 'Abbott', company: 'Abbott Laboratories', category: 'XSTOCK', sector: 'Healthcare', mintAddress: 'XsHtf5RpxsQ7jeJ9ivNewouZKJHbPxhPoEy6yYvULr7', description: 'Medical devices, diagnostics' },
    { ticker: 'TMOx', name: 'Thermo Fisher', company: 'Thermo Fisher Scientific', category: 'XSTOCK', sector: 'Healthcare', mintAddress: 'Xs8drBWy3Sd5QY3aifG9kt9KFs2K3PGZmx7jWrsrk57', description: 'Lab equipment, life sciences' },
    { ticker: 'DHRx', name: 'Danaher', company: 'Danaher Corp.', category: 'XSTOCK', sector: 'Healthcare', mintAddress: 'Xseo8tgCZfkHxWS9xbFYeKFyMSbWEvZGFV1Gh53GtCV', description: 'Life sciences, diagnostics' },
    { ticker: 'MDTx', name: 'Medtronic', company: 'Medtronic plc', category: 'XSTOCK', sector: 'Healthcare', mintAddress: 'XsDgw22qRLTv5Uwuzn6T63cW69exG41T6gwQhEK22u2', description: 'Medical technology' },
    { ticker: 'AZNx', name: 'AstraZeneca', company: 'AstraZeneca plc', category: 'XSTOCK', sector: 'Healthcare', mintAddress: 'Xs3ZFkPYT2BN7qBMqf1j1bfTeTm1rFzEFSsQ1z3wAKU', description: 'Biopharmaceuticals, oncology' },
    { ticker: 'NVOx', name: 'Novo Nordisk', company: 'Novo Nordisk A/S', category: 'XSTOCK', sector: 'Healthcare', mintAddress: 'XsfAzPzYrYjd4Dpa9BU3cusBsvWfVB9gBcyGC87S57n', description: 'Diabetes, obesity treatment (Ozempic)' },
    // === Consumer & Retail ===
    { ticker: 'KOx', name: 'Coca-Cola', company: 'Coca-Cola Co.', category: 'XSTOCK', sector: 'Consumer', mintAddress: 'XsaBXg8dU5cPM6ehmVctMkVqoiRG2ZjMo1cyBJ3AykQ', description: 'Beverages, global consumer brand' },
    { ticker: 'PEPx', name: 'PepsiCo', company: 'PepsiCo Inc.', category: 'XSTOCK', sector: 'Consumer', mintAddress: 'Xsv99frTRUeornyvCfvhnDesQDWuvns1M852Pez91vF', description: 'Beverages, snacks, Frito-Lay' },
    { ticker: 'MCDx', name: "McDonald's", company: "McDonald's Corp.", category: 'XSTOCK', sector: 'Consumer', mintAddress: 'XsqE9cRRpzxcGKDXj1BJ7Xmg4GRhZoyY1KpmGSxAWT2', description: 'Fast food restaurants, global franchise' },
    { ticker: 'WMTx', name: 'Walmart', company: 'Walmart Inc.', category: 'XSTOCK', sector: 'Retail', mintAddress: 'Xs151QeqTCiuKtinzfRATnUESM2xTU6V9Wy8Vy538ci', description: 'Retail, e-commerce, grocery' },
    { ticker: 'HDx', name: 'Home Depot', company: 'Home Depot Inc.', category: 'XSTOCK', sector: 'Retail', mintAddress: 'XszjVtyhowGjSC5odCqBpW1CtXXwXjYokymrk7fGKD3', description: 'Home improvement retail' },
    { ticker: 'PGx', name: 'P&G', company: 'Procter & Gamble', category: 'XSTOCK', sector: 'Consumer', mintAddress: 'XsYdjDjNUygZ7yGKfQaB6TxLh2gC6RRjzLtLAGJrhzV', description: 'Consumer staples, household brands' },
    { ticker: 'PMx', name: 'Philip Morris', company: 'Philip Morris Intl.', category: 'XSTOCK', sector: 'Consumer', mintAddress: 'Xsba6tUnSjDae2VcopDB6FGGDaxRrewFCDa5hKn5vT3', description: 'Tobacco, IQOS heated products' },
    // === Industrial & Energy ===
    { ticker: 'XOMx', name: 'ExxonMobil', company: 'Exxon Mobil Corp.', category: 'XSTOCK', sector: 'Energy', mintAddress: 'XsaHND8sHyfMfsWPj6kSdd5VwvCayZvjYgKmmcNL5qh', description: 'Oil & gas, integrated energy' },
    { ticker: 'CVXx', name: 'Chevron', company: 'Chevron Corp.', category: 'XSTOCK', sector: 'Energy', mintAddress: 'XsNNMt7WTNA2sV3jrb1NNfNgapxRF5i4i6GcnTRRHts', description: 'Oil & gas, energy' },
    { ticker: 'LINx', name: 'Linde', company: 'Linde plc', category: 'XSTOCK', sector: 'Industrial', mintAddress: 'XsSr8anD1hkvNMu8XQiVcmiaTP7XGvYu7Q58LdmtE8Z', description: 'Industrial gases, engineering' },
    { ticker: 'HONx', name: 'Honeywell', company: 'Honeywell Intl.', category: 'XSTOCK', sector: 'Industrial', mintAddress: 'XsRbLZthfABAPAfumWNEJhPyiKDW6TvDVeAeW7oKqA2', description: 'Aerospace, building tech, performance materials' },
    // === Media & Telecom ===
    { ticker: 'CMCSAx', name: 'Comcast', company: 'Comcast Corp.', category: 'XSTOCK', sector: 'Media', mintAddress: 'XsvKCaNsxg2GN8jjUmq71qukMJr7Q1c5R2Mk9P8kcS8', description: 'Cable, broadband, NBCUniversal' },
    { ticker: 'AMBRx', name: 'Amber', company: 'Amber Group', category: 'XSTOCK', sector: 'Crypto', mintAddress: 'XsaQTCgebC2KPbf27KUhdv5JFvHhQ4GDAPURwrEhAzb', description: 'Crypto financial services' },
    { ticker: 'CRCLx', name: 'Circle', company: 'Circle Internet', category: 'XSTOCK', sector: 'Crypto', mintAddress: 'XsueG8BtpquVJX9LVLLEGuViXUungE6WmK5YZ3p3bd1', description: 'USDC stablecoin issuer' },
];
// ============================================================================
// PreStocks — Tokenized pre-IPO equity exposure (SPV-backed)
// ============================================================================
export const PRESTOCKS = [
    { ticker: 'SPACEX', name: 'SpaceX', company: 'Space Exploration Technologies', category: 'PRESTOCK', sector: 'Aerospace', mintAddress: 'PreANxuXjsy2pvisWWMNB6YaJNzr7681wJJr2rHsfTh', description: 'Rocket launches, Starlink satellite internet, Mars colonization' },
    { ticker: 'OPENAI', name: 'OpenAI', company: 'OpenAI Inc.', category: 'PRESTOCK', sector: 'AI', mintAddress: 'PreweJYECqtQwBtpxHL171nL2K6umo692gTm7Q3rpgF', description: 'ChatGPT, GPT models, AGI research' },
    { ticker: 'ANTHROPIC', name: 'Anthropic', company: 'Anthropic PBC', category: 'PRESTOCK', sector: 'AI', mintAddress: 'Pren1FvFX6J3E4kXhJuCiAD5aDmGEb7qJRncwA8Lkhw', description: 'Claude AI, constitutional AI, safety-focused' },
    { ticker: 'XAI', name: 'xAI', company: 'xAI Corp.', category: 'PRESTOCK', sector: 'AI', mintAddress: 'PreC1KtJ1sBPPqaeeqL6Qb15GTLCYVvyYEwxhdfTwfx', description: 'Grok AI, Elon Musk AI venture' },
    { ticker: 'ANDURIL', name: 'Anduril', company: 'Anduril Industries', category: 'PRESTOCK', sector: 'Defense', mintAddress: 'PresTj4Yc2bAR197Er7wz4UUKSfqt6FryBEdAriBoQB', description: 'Defense technology, autonomous systems, Lattice OS' },
    { ticker: 'KALSHI', name: 'Kalshi', company: 'Kalshi Inc.', category: 'PRESTOCK', sector: 'Fintech', mintAddress: 'PreLWGkkeqG1s4HEfFZSy9moCrJ7btsHuUtfcCeoRua', description: 'Event-based prediction markets, CFTC-regulated' },
    { ticker: 'POLYMARKET', name: 'Polymarket', company: 'Polymarket Inc.', category: 'PRESTOCK', sector: 'Fintech', mintAddress: 'Pre8AREmFPtoJFT8mQSXQLh56cwJmM7CFDRuoGBZiUP', description: 'Prediction markets, information markets' },
];
// ============================================================================
// Indexes — Tokenized market indexes
// ============================================================================
export const INDEXES = [
    { ticker: 'SPYx', name: 'S&P 500', company: 'SPDR S&P 500 ETF', category: 'INDEX', sector: 'Index', mintAddress: 'XsoCS1TfEyfFhfvj8EtZ528L3CaKBDBRqRapnBbDF2W', description: '500 largest US public companies' },
    { ticker: 'QQQx', name: 'Nasdaq 100', company: 'Invesco QQQ Trust', category: 'INDEX', sector: 'Index', mintAddress: 'Xs8S1uUs1zvS2p7iwtsG3b6fkhpvmwz4GYU3gWAmWHZ', description: 'Top 100 non-financial Nasdaq stocks' },
    { ticker: 'TQQQx', name: 'TQQQ', company: 'ProShares UltraPro QQQ', category: 'INDEX', sector: 'Index', mintAddress: 'XsjQP3iMAaQ3kQScQKthQpx9ALRbjKAjQtHg6TFomoc', description: '3x leveraged Nasdaq 100' },
    { ticker: 'VTIx', name: 'Vanguard Total', company: 'Vanguard Total Market ETF', category: 'INDEX', sector: 'Index', mintAddress: 'XsssYEQjzxBCFgvYFFNuhJFBeHNdLWYeUSP8P45cDr9', description: 'Total US stock market exposure' },
    { ticker: 'TBLLx', name: 'T-Bills', company: 'US Treasury Bills ETF', category: 'INDEX', sector: 'Fixed Income', mintAddress: 'XsqBC5tcVQLYt8wqGCHRnAUUecbRYXoJCReD6w7QEKp', description: 'Short-term US treasury exposure' },
];
// ============================================================================
// Commodities — Tokenized precious metals
// ============================================================================
export const COMMODITIES_TOKENS = [
    { ticker: 'GLDx', name: 'Gold', company: 'SPDR Gold Shares', category: 'COMMODITY', sector: 'Precious Metals', mintAddress: 'Xsv9hRk1z5ystj9MhnA7Lq4vjSsLwzL2nxrwmwtD3re', description: 'Physical gold-backed ETF' },
];
// ============================================================================
// Combined registry
// ============================================================================
export const ALL_TOKENIZED_EQUITIES = [
    ...XSTOCKS,
    ...PRESTOCKS,
    ...INDEXES,
    ...COMMODITIES_TOKENS,
];
// Quick lookup by mint address
export const EQUITY_BY_MINT = new Map(ALL_TOKENIZED_EQUITIES.map(eq => [eq.mintAddress, eq]));
// Quick lookup by ticker
export const EQUITY_BY_TICKER = new Map(ALL_TOKENIZED_EQUITIES.map(eq => [eq.ticker, eq]));
// Sector groupings for UI display
export const SECTORS = [
    'Technology', 'Cybersecurity', 'Entertainment', 'Auto & EV',
    'Finance', 'Crypto', 'Healthcare', 'Consumer', 'Retail',
    'Energy', 'Industrial', 'Media', 'Aerospace', 'AI',
    'Defense', 'Fintech', 'Index', 'Fixed Income', 'Precious Metals',
];
