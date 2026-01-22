/**
 * Login Page - Beautiful Authentication UI
 * Matches jarvislife.io premium design with glassmorphism
 */
import React, { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { LogIn, Mail, Lock, AlertCircle, Eye, EyeOff, Sparkles } from 'lucide-react';
import { GlassCard } from '../UI/GlassCard';
import clsx from 'clsx';

export const LoginPage: React.FC = () => {
  const navigate = useNavigate();
  const [formData, setFormData] = useState({
    email: '',
    password: '',
  });
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setLoading(true);

    try {
      const response = await fetch('/api/auth/login', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(formData),
      });

      if (!response.ok) {
        const data = await response.json();
        throw new Error(data.detail || 'Login failed');
      }

      const data = await response.json();

      // Store tokens
      localStorage.setItem('access_token', data.access_token);
      localStorage.setItem('refresh_token', data.refresh_token);

      // Navigate to dashboard
      navigate('/dashboard');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Login failed');
    } finally {
      setLoading(false);
    }
  };

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setFormData({
      ...formData,
      [e.target.name]: e.target.value,
    });
  };

  return (
    <div className="min-h-screen flex items-center justify-center p-6 relative overflow-hidden">
      {/* Animated Background */}
      <div className="absolute inset-0 opacity-30">
        <div className="absolute top-1/4 left-1/4 w-96 h-96 bg-accent/10 rounded-full blur-3xl animate-pulse" />
        <div className="absolute bottom-1/4 right-1/4 w-96 h-96 bg-accent/10 rounded-full blur-3xl animate-pulse" style={{ animationDelay: '1s' }} />
      </div>

      <div className="relative z-10 w-full max-w-md">
        {/* Logo & Title */}
        <div className="text-center mb-8 fade-in">
          <div className="mb-4 inline-block p-4 bg-accent/10 rounded-2xl">
            <Sparkles className="w-12 h-12 text-accent animate-pulse" />
          </div>
          <h1 className="text-4xl font-display font-bold mb-2 glow-text">
            JARVIS AI
          </h1>
          <p className="text-muted">
            AI-Powered Solana Trading Platform
          </p>
        </div>

        {/* Login Card */}
        <GlassCard className="fade-in" style={{ animationDelay: '0.1s' }}>
          <div className="mb-6">
            <h2 className="text-2xl font-display font-semibold mb-2">
              Welcome Back
            </h2>
            <p className="text-muted text-sm">
              Sign in to continue trading with AI insights
            </p>
          </div>

          {/* Error Message */}
          {error && (
            <div className="mb-4 p-3 bg-error/10 border border-error/30 rounded-lg flex items-start gap-2">
              <AlertCircle className="text-error flex-shrink-0 mt-0.5" size={16} />
              <p className="text-sm text-error">{error}</p>
            </div>
          )}

          {/* Login Form */}
          <form onSubmit={handleSubmit} className="space-y-4">
            {/* Email Input */}
            <div>
              <label htmlFor="email" className="block text-sm font-medium mb-2">
                Email Address
              </label>
              <div className="relative">
                <input
                  id="email"
                  name="email"
                  type="email"
                  required
                  value={formData.email}
                  onChange={handleChange}
                  className="input pl-10"
                  placeholder="you@example.com"
                  disabled={loading}
                />
                <Mail
                  className="absolute left-3 top-1/2 -translate-y-1/2 text-muted"
                  size={18}
                />
              </div>
            </div>

            {/* Password Input */}
            <div>
              <label htmlFor="password" className="block text-sm font-medium mb-2">
                Password
              </label>
              <div className="relative">
                <input
                  id="password"
                  name="password"
                  type={showPassword ? 'text' : 'password'}
                  required
                  value={formData.password}
                  onChange={handleChange}
                  className="input pl-10 pr-10"
                  placeholder="••••••••"
                  disabled={loading}
                />
                <Lock
                  className="absolute left-3 top-1/2 -translate-y-1/2 text-muted"
                  size={18}
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-muted hover:text-text-primary transition-colors"
                  tabIndex={-1}
                >
                  {showPassword ? <EyeOff size={18} /> : <Eye size={18} />}
                </button>
              </div>
            </div>

            {/* Remember Me & Forgot Password */}
            <div className="flex items-center justify-between">
              <label className="flex items-center gap-2 cursor-pointer">
                <input
                  type="checkbox"
                  className="w-4 h-4 rounded border-border bg-surface checked:bg-accent checked:border-accent"
                />
                <span className="text-sm text-muted">Remember me</span>
              </label>
              <Link
                to="/forgot-password"
                className="text-sm text-accent hover:underline"
              >
                Forgot password?
              </Link>
            </div>

            {/* Submit Button */}
            <button
              type="submit"
              disabled={loading}
              className={clsx(
                'btn btn-primary w-full',
                loading && 'opacity-50 cursor-not-allowed'
              )}
            >
              {loading ? (
                <>
                  <div className="animate-spin">⏳</div>
                  <span>Signing in...</span>
                </>
              ) : (
                <>
                  <LogIn size={18} />
                  <span>Sign In</span>
                </>
              )}
            </button>
          </form>

          {/* Divider */}
          <div className="my-6 flex items-center gap-4">
            <div className="flex-1 h-px bg-border" />
            <span className="text-xs text-muted uppercase">Or</span>
            <div className="flex-1 h-px bg-border" />
          </div>

          {/* Social Login (Future) */}
          <div className="space-y-2">
            <button
              className="btn btn-secondary w-full"
              disabled
            >
              <img src="/icons/google.svg" alt="Google" className="w-5 h-5" />
              <span>Continue with Google</span>
              <span className="ml-auto text-xs text-muted">(Soon)</span>
            </button>
          </div>

          {/* Sign Up Link */}
          <div className="mt-6 text-center">
            <p className="text-sm text-muted">
              Don't have an account?{' '}
              <Link to="/register" className="text-accent hover:underline font-semibold">
                Sign up
              </Link>
            </p>
          </div>
        </GlassCard>

        {/* Security Notice */}
        <div className="mt-6 text-center text-xs text-muted fade-in" style={{ animationDelay: '0.2s' }}>
          🔒 Secured with bank-level encryption
        </div>
      </div>
    </div>
  );
};
