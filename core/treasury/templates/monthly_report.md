# Treasury Monthly Report

**Report Period:** {{ month_name }} {{ year }}
**Generated:** {{ generated_at }}

---

## Executive Summary

### Key Performance Indicators

| Metric | This Month | Last Month | YTD |
|--------|------------|------------|-----|
| Treasury Value | ${{ current_value | format_usd }} | ${{ last_month_value | format_usd }} | - |
| Monthly P&L | ${{ monthly_pnl | format_usd }} | ${{ last_month_pnl | format_usd }} | ${{ ytd_pnl | format_usd }} |
| Total Return | {{ monthly_return | format_percent }} | {{ last_month_return | format_percent }} | {{ ytd_return | format_percent }} |
| Total Trades | {{ trade_count }} | {{ last_month_trades }} | {{ ytd_trades }} |
| Win Rate | {{ win_rate | format_percent }} | {{ last_month_winrate | format_percent }} | {{ ytd_winrate | format_percent }} |

### Monthly Highlights

- {{ highlight_1 }}
- {{ highlight_2 }}
- {{ highlight_3 }}

---

## Portfolio Composition

### Asset Allocation

| Asset | Amount | USD Value | % of Portfolio |
|-------|--------|-----------|----------------|
{% for asset in assets %}
| {{ asset.token }} | {{ asset.amount | format_amount }} | ${{ asset.usd_value | format_usd }} | {{ asset.percent | format_percent }} |
{% endfor %}

### Allocation by Type

| Category | USD Value | % of Portfolio |
|----------|-----------|----------------|
| Stablecoins | ${{ stablecoin_value | format_usd }} | {{ stablecoin_percent | format_percent }} |
| Blue Chips | ${{ bluechip_value | format_usd }} | {{ bluechip_percent | format_percent }} |
| Trading Capital | ${{ trading_value | format_usd }} | {{ trading_percent | format_percent }} |
| Staked Assets | ${{ staked_value | format_usd }} | {{ staked_percent | format_percent }} |

---

## Trading Performance

### Monthly Statistics

| Metric | Value |
|--------|-------|
| Total Trades | {{ total_trades }} |
| Winning Trades | {{ winning_trades }} |
| Losing Trades | {{ losing_trades }} |
| Win Rate | {{ win_rate | format_percent }} |
| Average Win | ${{ avg_win | format_usd }} |
| Average Loss | ${{ avg_loss | format_usd }} |
| Profit Factor | {{ profit_factor | format_number(2) }} |
| Largest Win | ${{ largest_win | format_usd }} |
| Largest Loss | ${{ largest_loss | format_usd }} |

### Strategy Performance

| Strategy | Trades | Win Rate | Gross P&L | Net P&L | Sharpe |
|----------|--------|----------|-----------|---------|--------|
{% for strategy in strategies %}
| {{ strategy.name }} | {{ strategy.trades }} | {{ strategy.win_rate | format_percent }} | ${{ strategy.gross_pnl | format_usd }} | ${{ strategy.net_pnl | format_usd }} | {{ strategy.sharpe | format_number(2) }} |
{% endfor %}

### Weekly Breakdown

| Week | Trades | P&L | Win Rate |
|------|--------|-----|----------|
{% for week in weeks %}
| Week {{ week.number }} ({{ week.dates }}) | {{ week.trades }} | ${{ week.pnl | format_usd }} | {{ week.win_rate | format_percent }} |
{% endfor %}

---

## Token Distribution

### Staking Rewards

| Week | Amount Distributed | Recipients | Avg per Staker |
|------|-------------------|------------|----------------|
{% for week in staking_weeks %}
| {{ week.date }} | {{ week.amount | format_amount }} | {{ week.recipients }} | {{ week.avg_per_staker | format_amount }} |
{% endfor %}

**Monthly Total:** {{ staking_total | format_amount }} tokens to {{ staking_recipients }} stakers

### Buyback & Burn

| Date | Amount Burned | USD Value | Tx |
|------|--------------|-----------|-----|
{% for burn in burns %}
| {{ burn.date }} | {{ burn.amount | format_amount }} | ${{ burn.usd_value | format_usd }} | {{ burn.tx_short }} |
{% endfor %}

**Monthly Total:** {{ burn_total | format_amount }} tokens burned (${{ burn_total_usd | format_usd }})

---

## Risk Analysis

### Risk Metrics

| Metric | Value | Benchmark | Status |
|--------|-------|-----------|--------|
| Max Drawdown | {{ max_drawdown | format_percent }} | < 15% | {{ drawdown_status }} |
| Sharpe Ratio | {{ sharpe_ratio | format_number(2) }} | > 1.5 | {{ sharpe_status }} |
| Sortino Ratio | {{ sortino_ratio | format_number(2) }} | > 2.0 | {{ sortino_status }} |
| Calmar Ratio | {{ calmar_ratio | format_number(2) }} | > 1.0 | {{ calmar_status }} |
| Daily VaR (95%) | ${{ var_95 | format_usd }} | - | {{ var_status }} |
| Beta (vs SOL) | {{ beta | format_number(2) }} | < 1.0 | {{ beta_status }} |

### Drawdown Analysis

| Drawdown Period | Max DD | Duration | Recovery |
|-----------------|--------|----------|----------|
{% for dd in drawdowns %}
| {{ dd.start_date }} - {{ dd.end_date }} | {{ dd.max_drawdown | format_percent }} | {{ dd.duration_days }} days | {{ dd.recovery_days }} days |
{% endfor %}

---

## Market Analysis

### Market Conditions

{{ market_summary }}

### Correlation with Market

| Asset | Correlation |
|-------|-------------|
| BTC | {{ btc_correlation | format_number(2) }} |
| ETH | {{ eth_correlation | format_number(2) }} |
| SOL | {{ sol_correlation | format_number(2) }} |

---

## Outlook & Strategy

### Next Month Focus

{{ next_month_strategy }}

### Risk Adjustments

{{ risk_adjustments }}

### Action Items

{% for item in action_items %}
- [ ] {{ item }}
{% endfor %}

---

## Appendix

### Transaction Log

See attached CSV file: `transactions_{{ month_name }}_{{ year }}.csv`

### Audit Trail

All transactions are verifiable on-chain:
- Treasury Hot Wallet: `{{ hot_wallet }}`
- Treasury Cold Wallet: `{{ cold_wallet }}`
- Multisig: `{{ multisig_address }}`

---

*This report was automatically generated by JARVIS Treasury Management System.*
*Report ID: {{ report_id }}*
*Checksum: {{ checksum }}*
