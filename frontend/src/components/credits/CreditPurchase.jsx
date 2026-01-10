/**
 * Credit Purchase Component
 *
 * Interface for purchasing API credits via Stripe:
 * - Package selection (Starter, Pro, Whale)
 * - Stripe checkout integration
 * - Balance display
 * - Purchase history
 */

import React, { useState, useEffect, useCallback } from 'react';

// =============================================================================
// Sub-components
// =============================================================================

const PackageCard = ({
  name,
  credits,
  bonus,
  price,
  points,
  selected,
  onSelect,
  popular,
}) => (
  <div
    className={`package-card ${selected ? 'selected' : ''} ${popular ? 'popular' : ''}`}
    onClick={onSelect}
  >
    {popular && <div className="popular-badge">Most Popular</div>}
    <h3 className="package-name">{name}</h3>
    <div className="package-credits">
      <span className="credit-amount">{credits.toLocaleString()}</span>
      <span className="credit-label">credits</span>
    </div>
    {bonus > 0 && (
      <div className="package-bonus">+{bonus.toLocaleString()} bonus</div>
    )}
    <div className="package-price">
      <span className="price-currency">$</span>
      <span className="price-amount">{(price / 100).toFixed(0)}</span>
    </div>
    <div className="package-points">
      +{points} loyalty points
    </div>
    <div className="package-value">
      ${((price / 100) / (credits + bonus) * 100).toFixed(2)} per 100 credits
    </div>
  </div>
);

const BalanceDisplay = ({ balance, lifetime, points }) => (
  <div className="balance-display">
    <div className="balance-item current">
      <span className="balance-label">Current Balance</span>
      <span className="balance-value">{balance?.toLocaleString() || 0}</span>
      <span className="balance-unit">credits</span>
    </div>
    <div className="balance-item lifetime">
      <span className="balance-label">Lifetime</span>
      <span className="balance-value">{lifetime?.toLocaleString() || 0}</span>
    </div>
    <div className="balance-item points">
      <span className="balance-label">Points</span>
      <span className="balance-value">{points?.toLocaleString() || 0}</span>
    </div>
  </div>
);

const UsageChart = ({ usage }) => {
  if (!usage || usage.length === 0) return null;

  const maxUsage = Math.max(...usage.map((u) => u.credits));

  return (
    <div className="usage-chart">
      <h4>Usage (Last 7 Days)</h4>
      <div className="chart-bars">
        {usage.map((day, i) => (
          <div key={i} className="chart-bar-container">
            <div
              className="chart-bar"
              style={{ height: `${(day.credits / maxUsage) * 100}%` }}
            />
            <span className="chart-label">{day.date}</span>
          </div>
        ))}
      </div>
    </div>
  );
};

const TransactionHistory = ({ transactions }) => (
  <div className="transaction-history">
    <h4>Recent Transactions</h4>
    <table>
      <thead>
        <tr>
          <th>Date</th>
          <th>Type</th>
          <th>Amount</th>
          <th>Balance</th>
        </tr>
      </thead>
      <tbody>
        {transactions.map((tx, i) => (
          <tr key={i} className={tx.amount > 0 ? 'credit' : 'debit'}>
            <td>{new Date(tx.created_at).toLocaleDateString()}</td>
            <td>{tx.transaction_type}</td>
            <td>{tx.amount > 0 ? '+' : ''}{tx.amount}</td>
            <td>{tx.balance_after}</td>
          </tr>
        ))}
      </tbody>
    </table>
  </div>
);

// =============================================================================
// Main Component
// =============================================================================

const CreditPurchase = ({ user, onBalanceUpdate }) => {
  // State
  const [packages, setPackages] = useState([]);
  const [balance, setBalance] = useState(null);
  const [transactions, setTransactions] = useState([]);
  const [usage, setUsage] = useState([]);
  const [selectedPackage, setSelectedPackage] = useState(null);

  // UI State
  const [loading, setLoading] = useState(true);
  const [checkoutLoading, setCheckoutLoading] = useState(false);
  const [error, setError] = useState(null);
  const [success, setSuccess] = useState(null);

  // API base URL
  const API_URL = process.env.REACT_APP_API_URL || '';

  // Default packages (fallback)
  const defaultPackages = [
    {
      id: 'starter',
      name: 'Starter',
      credits: 100,
      bonus: 0,
      price: 2500,
      points: 25,
    },
    {
      id: 'pro',
      name: 'Pro',
      credits: 500,
      bonus: 50,
      price: 10000,
      points: 150,
      popular: true,
    },
    {
      id: 'whale',
      name: 'Whale',
      credits: 3000,
      bonus: 500,
      price: 50000,
      points: 1000,
    },
  ];

  // ==========================================================================
  // Data Fetching
  // ==========================================================================

  const fetchData = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);

      // Fetch packages
      const packagesRes = await fetch(`${API_URL}/api/credits/packages`);
      const packagesJson = await packagesRes.json();

      // Fetch balance
      const balanceRes = await fetch(`${API_URL}/api/credits/balance`, {
        headers: {
          Authorization: `Bearer ${user?.token}`,
        },
      });
      const balanceJson = await balanceRes.json();

      // Fetch transactions
      const txRes = await fetch(`${API_URL}/api/credits/transactions?limit=10`, {
        headers: {
          Authorization: `Bearer ${user?.token}`,
        },
      });
      const txJson = await txRes.json();

      // Fetch usage
      const usageRes = await fetch(`${API_URL}/api/credits/usage?days=7`, {
        headers: {
          Authorization: `Bearer ${user?.token}`,
        },
      });
      const usageJson = await usageRes.json();

      setPackages(packagesJson.packages || defaultPackages);
      setBalance(balanceJson);
      setTransactions(txJson.transactions || []);
      setUsage(usageJson.daily || []);

      // Pre-select Pro package
      setSelectedPackage('pro');

    } catch (err) {
      console.error('Failed to fetch credit data:', err);
      setPackages(defaultPackages);
      setError('Failed to load data');
    } finally {
      setLoading(false);
    }
  }, [user, API_URL]);

  useEffect(() => {
    if (user) {
      fetchData();
    }
  }, [fetchData, user]);

  // Check for successful payment return
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    if (params.get('payment') === 'success') {
      setSuccess('Payment successful! Credits have been added to your account.');
      fetchData();
      // Clean URL
      window.history.replaceState({}, '', window.location.pathname);
    } else if (params.get('payment') === 'cancelled') {
      setError('Payment was cancelled.');
      window.history.replaceState({}, '', window.location.pathname);
    }
  }, [fetchData]);

  // ==========================================================================
  // Checkout
  // ==========================================================================

  const handleCheckout = async () => {
    if (!selectedPackage) {
      setError('Please select a package');
      return;
    }

    setCheckoutLoading(true);
    setError(null);

    try {
      const res = await fetch(`${API_URL}/api/credits/checkout`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${user?.token}`,
        },
        body: JSON.stringify({
          package_id: selectedPackage,
          success_url: `${window.location.origin}${window.location.pathname}?payment=success`,
          cancel_url: `${window.location.origin}${window.location.pathname}?payment=cancelled`,
        }),
      });

      const data = await res.json();

      if (data.checkout_url) {
        // Redirect to Stripe Checkout
        window.location.href = data.checkout_url;
      } else {
        setError(data.error || 'Failed to create checkout session');
      }
    } catch (err) {
      setError('Checkout failed: ' + err.message);
    } finally {
      setCheckoutLoading(false);
    }
  };

  // ==========================================================================
  // Render
  // ==========================================================================

  if (!user) {
    return (
      <div className="credit-login-prompt">
        <h2>Sign In Required</h2>
        <p>Please sign in to purchase credits and view your balance.</p>
      </div>
    );
  }

  if (loading) {
    return (
      <div className="credit-loading">
        <div className="spinner-large" />
        <p>Loading credit information...</p>
      </div>
    );
  }

  return (
    <div className="credit-purchase">
      {/* Notifications */}
      {error && <div className="alert alert-error">{error}</div>}
      {success && <div className="alert alert-success">{success}</div>}

      {/* Header */}
      <div className="credit-header">
        <h1>API Credits</h1>
        <p>Purchase credits to access JARVIS trading and analysis APIs</p>
      </div>

      {/* Balance */}
      <BalanceDisplay
        balance={balance?.balance}
        lifetime={balance?.lifetime_credits}
        points={balance?.points}
      />

      {/* Package Selection */}
      <div className="packages-section">
        <h2>Select a Package</h2>
        <div className="packages-grid">
          {packages.map((pkg) => (
            <PackageCard
              key={pkg.id}
              name={pkg.name}
              credits={pkg.credits}
              bonus={pkg.bonus}
              price={pkg.price}
              points={pkg.points}
              popular={pkg.popular}
              selected={selectedPackage === pkg.id}
              onSelect={() => setSelectedPackage(pkg.id)}
            />
          ))}
        </div>
      </div>

      {/* Checkout Button */}
      <div className="checkout-section">
        <button
          className="checkout-button"
          onClick={handleCheckout}
          disabled={!selectedPackage || checkoutLoading}
        >
          {checkoutLoading ? (
            <span className="spinner" />
          ) : (
            <>
              Purchase{' '}
              {packages.find((p) => p.id === selectedPackage)?.name || 'Package'}
            </>
          )}
        </button>
        <p className="checkout-note">
          Secure payment powered by Stripe. Credits are added instantly.
        </p>
      </div>

      {/* Credit Costs */}
      <div className="credit-costs">
        <h3>API Credit Costs</h3>
        <table>
          <thead>
            <tr>
              <th>Endpoint</th>
              <th>Cost</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td>/api/trade/quote</td>
              <td>1 credit</td>
            </tr>
            <tr>
              <td>/api/trade/execute</td>
              <td>5 credits</td>
            </tr>
            <tr>
              <td>/api/analyze</td>
              <td>10 credits</td>
            </tr>
            <tr>
              <td>/api/backtest</td>
              <td>50 credits</td>
            </tr>
          </tbody>
        </table>
      </div>

      {/* Rate Limits */}
      <div className="rate-limits">
        <h3>Rate Limits by Tier</h3>
        <table>
          <thead>
            <tr>
              <th>Tier</th>
              <th>Requests/Min</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td>Free</td>
              <td>10</td>
            </tr>
            <tr>
              <td>Starter</td>
              <td>50</td>
            </tr>
            <tr>
              <td>Pro</td>
              <td>100</td>
            </tr>
            <tr>
              <td>Whale</td>
              <td>500</td>
            </tr>
          </tbody>
        </table>
      </div>

      {/* Usage Chart */}
      <UsageChart usage={usage} />

      {/* Transaction History */}
      {transactions.length > 0 && (
        <TransactionHistory transactions={transactions} />
      )}
    </div>
  );
};

export default CreditPurchase;
