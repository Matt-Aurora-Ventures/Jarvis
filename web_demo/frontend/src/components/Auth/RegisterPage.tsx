/**
 * Register Page - Beautiful Sign Up UI
 * Matches jarvislife.io premium design with enhanced validations
 */
import React, { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { UserPlus, Mail, Lock, User, AlertCircle, Eye, EyeOff, Check, X, Sparkles } from 'lucide-react';
import { GlassCard } from '../UI/GlassCard';
import clsx from 'clsx';

interface PasswordStrength {
  score: number;
  label: string;
  color: string;
  checks: {
    length: boolean;
    uppercase: boolean;
    lowercase: boolean;
    number: boolean;
    special: boolean;
  };
}

export const RegisterPage: React.FC = () => {
  const navigate = useNavigate();
  const [formData, setFormData] = useState({
    email: '',
    username: '',
    password: '',
    confirmPassword: '',
  });
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const getPasswordStrength = (password: string): PasswordStrength => {
    const checks = {
      length: password.length >= 12,
      uppercase: /[A-Z]/.test(password),
      lowercase: /[a-z]/.test(password),
      number: /[0-9]/.test(password),
      special: /[!@#$%^&*(),.?":{}|<>]/.test(password),
    };

    const score = Object.values(checks).filter(Boolean).length;

    let label = 'Weak';
    let color = 'error';

    if (score >= 5) {
      label = 'Very Strong';
      color = 'success';
    } else if (score >= 4) {
      label = 'Strong';
      color = 'success';
    } else if (score >= 3) {
      label = 'Fair';
      color = 'warning';
    }

    return { score, label, color, checks };
  };

  const passwordStrength = getPasswordStrength(formData.password);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    // Validate passwords match
    if (formData.password !== formData.confirmPassword) {
      setError('Passwords do not match');
      return;
    }

    // Validate password strength
    if (passwordStrength.score < 5) {
      setError('Password does not meet all requirements');
      return;
    }

    setLoading(true);

    try {
      const response = await fetch('/api/auth/register', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          email: formData.email,
          username: formData.username,
          password: formData.password,
        }),
      });

      if (!response.ok) {
        const data = await response.json();
        throw new Error(data.detail || 'Registration failed');
      }

      const data = await response.json();

      // Store tokens
      localStorage.setItem('access_token', data.access_token);
      localStorage.setItem('refresh_token', data.refresh_token);

      // Navigate to dashboard
      navigate('/dashboard');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Registration failed');
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
        <div className="absolute top-1/4 right-1/4 w-96 h-96 bg-accent/10 rounded-full blur-3xl animate-pulse" />
        <div className="absolute bottom-1/4 left-1/4 w-96 h-96 bg-accent/10 rounded-full blur-3xl animate-pulse" style={{ animationDelay: '1s' }} />
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
            Start Trading with AI-Powered Insights
          </p>
        </div>

        {/* Register Card */}
        <GlassCard className="fade-in" style={{ animationDelay: '0.1s' }}>
          <div className="mb-6">
            <h2 className="text-2xl font-display font-semibold mb-2">
              Create Account
            </h2>
            <p className="text-muted text-sm">
              Join thousands of traders using AI to maximize profits
            </p>
          </div>

          {/* Error Message */}
          {error && (
            <div className="mb-4 p-3 bg-error/10 border border-error/30 rounded-lg flex items-start gap-2">
              <AlertCircle className="text-error flex-shrink-0 mt-0.5" size={16} />
              <p className="text-sm text-error">{error}</p>
            </div>
          )}

          {/* Register Form */}
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

            {/* Username Input */}
            <div>
              <label htmlFor="username" className="block text-sm font-medium mb-2">
                Username
              </label>
              <div className="relative">
                <input
                  id="username"
                  name="username"
                  type="text"
                  required
                  value={formData.username}
                  onChange={handleChange}
                  className="input pl-10"
                  placeholder="trader123"
                  disabled={loading}
                  minLength={3}
                  maxLength={20}
                  pattern="[a-zA-Z0-9_-]+"
                />
                <User
                  className="absolute left-3 top-1/2 -translate-y-1/2 text-muted"
                  size={18}
                />
              </div>
              <p className="mt-1 text-xs text-muted">
                3-20 characters, letters, numbers, _ and - only
              </p>
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
                  placeholder="••••••••••••"
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

              {/* Password Strength Meter */}
              {formData.password && (
                <div className="mt-2">
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-xs text-muted">Password Strength</span>
                    <span className={clsx(
                      'text-xs font-semibold',
                      passwordStrength.color === 'success' && 'text-success',
                      passwordStrength.color === 'warning' && 'text-warning',
                      passwordStrength.color === 'error' && 'text-error'
                    )}>
                      {passwordStrength.label}
                    </span>
                  </div>
                  <div className="flex gap-1">
                    {[1, 2, 3, 4, 5].map((level) => (
                      <div
                        key={level}
                        className={clsx(
                          'flex-1 h-1.5 rounded-full transition-all',
                          level <= passwordStrength.score
                            ? passwordStrength.color === 'success'
                              ? 'bg-success'
                              : passwordStrength.color === 'warning'
                              ? 'bg-warning'
                              : 'bg-error'
                            : 'bg-surface'
                        )}
                      />
                    ))}
                  </div>

                  {/* Password Requirements */}
                  <div className="mt-2 space-y-1">
                    {Object.entries(passwordStrength.checks).map(([key, met]) => (
                      <div key={key} className="flex items-center gap-2 text-xs">
                        {met ? (
                          <Check className="text-success" size={12} />
                        ) : (
                          <X className="text-muted" size={12} />
                        )}
                        <span className={met ? 'text-muted' : 'text-muted'}>
                          {key === 'length' && 'At least 12 characters'}
                          {key === 'uppercase' && 'One uppercase letter'}
                          {key === 'lowercase' && 'One lowercase letter'}
                          {key === 'number' && 'One number'}
                          {key === 'special' && 'One special character'}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>

            {/* Confirm Password Input */}
            <div>
              <label htmlFor="confirmPassword" className="block text-sm font-medium mb-2">
                Confirm Password
              </label>
              <div className="relative">
                <input
                  id="confirmPassword"
                  name="confirmPassword"
                  type={showPassword ? 'text' : 'password'}
                  required
                  value={formData.confirmPassword}
                  onChange={handleChange}
                  className={clsx(
                    'input pl-10',
                    formData.confirmPassword &&
                      formData.password !== formData.confirmPassword &&
                      'border-error'
                  )}
                  placeholder="••••••••••••"
                  disabled={loading}
                />
                <Lock
                  className="absolute left-3 top-1/2 -translate-y-1/2 text-muted"
                  size={18}
                />
              </div>
              {formData.confirmPassword && formData.password !== formData.confirmPassword && (
                <p className="mt-1 text-xs text-error">Passwords do not match</p>
              )}
            </div>

            {/* Terms Checkbox */}
            <div>
              <label className="flex items-start gap-2 cursor-pointer">
                <input
                  type="checkbox"
                  required
                  className="mt-1 w-4 h-4 rounded border-border bg-surface checked:bg-accent checked:border-accent"
                />
                <span className="text-sm text-muted">
                  I agree to the{' '}
                  <Link to="/terms" className="text-accent hover:underline">
                    Terms of Service
                  </Link>{' '}
                  and{' '}
                  <Link to="/privacy" className="text-accent hover:underline">
                    Privacy Policy
                  </Link>
                </span>
              </label>
            </div>

            {/* Submit Button */}
            <button
              type="submit"
              disabled={loading || passwordStrength.score < 5}
              className={clsx(
                'btn btn-primary w-full',
                (loading || passwordStrength.score < 5) && 'opacity-50 cursor-not-allowed'
              )}
            >
              {loading ? (
                <>
                  <div className="animate-spin">⏳</div>
                  <span>Creating account...</span>
                </>
              ) : (
                <>
                  <UserPlus size={18} />
                  <span>Create Account</span>
                </>
              )}
            </button>
          </form>

          {/* Sign In Link */}
          <div className="mt-6 text-center">
            <p className="text-sm text-muted">
              Already have an account?{' '}
              <Link to="/login" className="text-accent hover:underline font-semibold">
                Sign in
              </Link>
            </p>
          </div>
        </GlassCard>

        {/* Security Notice */}
        <div className="mt-6 text-center text-xs text-muted fade-in" style={{ animationDelay: '0.2s' }}>
          🔒 Your data is encrypted and secure
        </div>
      </div>
    </div>
  );
};
