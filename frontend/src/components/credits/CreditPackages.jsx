/**
 * Credit Packages Component
 *
 * Display available credit packages for purchase:
 * - Package tiers with pricing
 * - Bonus credits display
 * - Stripe checkout integration
 */

import React, { useState, useEffect } from 'react';

const API_BASE = '/api/credits';

// Credit packages with pricing
const PACKAGES = [
  {
    id: 'starter_25',
    name: 'Starter',
    credits: 100,
    price: 25,
    pricePerCredit: 0.25,
    bonus: 0,
    popular: false,
    description: 'Perfect for getting started',
    features: ['100 API credits', 'Valid for 30 days', 'Basic support'],
  },
  {
    id: 'pro_100',
    name: 'Pro',
    credits: 500,
    price: 100,
    pricePerCredit: 0.20,
    bonus: 50,
    popular: true,
    description: 'Most popular choice',
    features: ['500 API credits', '+50 bonus credits', 'Valid for 90 days', 'Priority support'],
  },
  {
    id: 'whale_500',
    name: 'Whale',
    credits: 3000,
    price: 500,
    pricePerCredit: 0.167,
    bonus: 500,
    popular: false,
    description: 'For power users',
    features: ['3,000 API credits', '+500 bonus credits', 'Never expires', 'VIP support', 'Early feature access'],
  },
];

export default function CreditPackages({ userId, currentTier, onPurchaseComplete }) {
  const [loading, setLoading] = useState(false);
  const [selectedPackage, setSelectedPackage] = useState(null);
  const [error, setError] = useState(null);

  const handlePurchase = async (pkg) => {
    setLoading(true);
    setSelectedPackage(pkg.id);
    setError(null);

    try {
      // Create Stripe checkout session
      const response = await fetch(`${API_BASE}/checkout`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: userId,
          package_id: pkg.id,
          success_url: `${window.location.origin}/credits?success=true`,
          cancel_url: `${window.location.origin}/credits?canceled=true`,
        }),
      });

      if (!response.ok) {
        const err = await response.json();
        throw new Error(err.error || 'Failed to create checkout session');
      }

      const { checkout_url } = await response.json();

      // Redirect to Stripe Checkout
      window.location.href = checkout_url;
    } catch (err) {
      console.error('Checkout error:', err);
      setError(err.message || 'Failed to start checkout');
      setLoading(false);
      setSelectedPackage(null);
    }
  };

  // Check for success/canceled from URL
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    if (params.get('success') === 'true') {
      onPurchaseComplete?.();
      // Clean up URL
      window.history.replaceState({}, '', '/credits');
    }
  }, [onPurchaseComplete]);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="text-center mb-8">
        <h2 className="text-2xl font-bold text-white mb-2">Choose Your Credit Package</h2>
        <p className="text-gray-400">
          Purchase credits to access advanced trading features. Pay with any major credit card.
        </p>
      </div>

      {/* Packages Grid */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {PACKAGES.map((pkg) => (
          <PackageCard
            key={pkg.id}
            package={pkg}
            onSelect={() => handlePurchase(pkg)}
            loading={loading && selectedPackage === pkg.id}
            disabled={loading}
          />
        ))}
      </div>

      {/* Error Display */}
      {error && (
        <div className="bg-red-900/30 border border-red-700 rounded-lg p-4 text-red-400">
          {error}
        </div>
      )}

      {/* Trust Badges */}
      <div className="flex flex-wrap justify-center gap-6 pt-6 border-t border-gray-700">
        <TrustBadge icon="🔒" text="Secure Checkout" />
        <TrustBadge icon="💳" text="Powered by Stripe" />
        <TrustBadge icon="↩️" text="Instant Delivery" />
        <TrustBadge icon="📧" text="Email Receipt" />
      </div>

      {/* FAQ */}
      <div className="pt-6 border-t border-gray-700">
        <h3 className="text-lg font-semibold text-white mb-4">Frequently Asked Questions</h3>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <FAQItem
            question="What are credits used for?"
            answer="Credits are consumed when you use premium features like executing trades, running analysis, and accessing advanced signals."
          />
          <FAQItem
            question="Do credits expire?"
            answer="Starter credits expire after 30 days, Pro credits after 90 days. Whale credits never expire."
          />
          <FAQItem
            question="Can I get a refund?"
            answer="Unused credits can be refunded within 14 days of purchase. Contact support for assistance."
          />
          <FAQItem
            question="What payment methods are accepted?"
            answer="We accept all major credit cards (Visa, Mastercard, Amex) and Apple Pay through Stripe."
          />
        </div>
      </div>
    </div>
  );
}

// Package card component
function PackageCard({ package: pkg, onSelect, loading, disabled }) {
  return (
    <div className={`relative bg-gray-700/50 rounded-xl p-6 border ${
      pkg.popular
        ? 'border-blue-500 ring-2 ring-blue-500/20'
        : 'border-gray-600'
    }`}>
      {/* Popular Badge */}
      {pkg.popular && (
        <div className="absolute -top-3 left-1/2 -translate-x-1/2">
          <span className="bg-blue-600 text-white text-xs font-bold px-3 py-1 rounded-full">
            MOST POPULAR
          </span>
        </div>
      )}

      {/* Package Header */}
      <div className="text-center mb-6 pt-2">
        <h3 className="text-xl font-bold text-white mb-1">{pkg.name}</h3>
        <p className="text-sm text-gray-400">{pkg.description}</p>
      </div>

      {/* Price */}
      <div className="text-center mb-6">
        <div className="flex items-baseline justify-center gap-1">
          <span className="text-4xl font-bold text-white">${pkg.price}</span>
          <span className="text-gray-400">USD</span>
        </div>
        <div className="text-sm text-gray-400 mt-1">
          ${pkg.pricePerCredit.toFixed(2)} per credit
        </div>
      </div>

      {/* Credits */}
      <div className="bg-gray-800 rounded-lg p-4 mb-6">
        <div className="flex justify-between items-center">
          <span className="text-gray-400">Credits</span>
          <span className="text-white font-bold">{pkg.credits.toLocaleString()}</span>
        </div>
        {pkg.bonus > 0 && (
          <div className="flex justify-between items-center mt-2 text-green-400">
            <span>Bonus</span>
            <span className="font-bold">+{pkg.bonus.toLocaleString()}</span>
          </div>
        )}
        <div className="flex justify-between items-center mt-2 pt-2 border-t border-gray-700">
          <span className="text-white font-semibold">Total</span>
          <span className="text-white font-bold">
            {(pkg.credits + pkg.bonus).toLocaleString()}
          </span>
        </div>
      </div>

      {/* Features */}
      <ul className="space-y-2 mb-6">
        {pkg.features.map((feature, index) => (
          <li key={index} className="flex items-center gap-2 text-sm text-gray-300">
            <svg className="w-4 h-4 text-green-400 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
            </svg>
            {feature}
          </li>
        ))}
      </ul>

      {/* Purchase Button */}
      <button
        onClick={onSelect}
        disabled={loading || disabled}
        className={`w-full py-3 rounded-lg font-semibold transition-all ${
          pkg.popular
            ? 'bg-blue-600 hover:bg-blue-500 text-white'
            : 'bg-gray-600 hover:bg-gray-500 text-white'
        } disabled:opacity-50 disabled:cursor-not-allowed`}
      >
        {loading ? (
          <span className="flex items-center justify-center gap-2">
            <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-white"></div>
            Processing...
          </span>
        ) : (
          `Buy ${pkg.name}`
        )}
      </button>
    </div>
  );
}

// Trust badge component
function TrustBadge({ icon, text }) {
  return (
    <div className="flex items-center gap-2 text-gray-400">
      <span className="text-lg">{icon}</span>
      <span className="text-sm">{text}</span>
    </div>
  );
}

// FAQ item component
function FAQItem({ question, answer }) {
  return (
    <div className="bg-gray-700/30 rounded-lg p-4">
      <h4 className="text-sm font-semibold text-white mb-2">{question}</h4>
      <p className="text-sm text-gray-400">{answer}</p>
    </div>
  );
}
