/**
 * Onboarding Flow
 * Prompt #49: Step-by-step user onboarding wizard
 */

import React, { useState, useEffect, useCallback } from 'react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription, CardFooter } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Badge } from '@/components/ui/badge';
import { Progress } from '@/components/ui/progress';
import { Checkbox } from '@/components/ui/checkbox';
import { RadioGroup, RadioGroupItem } from '@/components/ui/radio-group';
import {
  Wallet,
  Rocket,
  Shield,
  Coins,
  ArrowRight,
  ArrowLeft,
  Check,
  Sparkles,
  Brain,
  Lock,
  TrendingUp,
  Gift,
  Zap,
  ChevronRight,
  ExternalLink,
  Copy,
  CheckCircle2
} from 'lucide-react';

// =============================================================================
// TYPES
// =============================================================================

interface OnboardingStep {
  id: string;
  title: string;
  description: string;
  icon: React.ElementType;
  component: React.ComponentType<StepProps>;
}

interface StepProps {
  data: OnboardingData;
  updateData: (data: Partial<OnboardingData>) => void;
  onNext: () => void;
  onBack: () => void;
  isFirstStep: boolean;
  isLastStep: boolean;
}

interface OnboardingData {
  wallet: string | null;
  experience: 'beginner' | 'intermediate' | 'advanced' | null;
  interests: string[];
  riskTolerance: 'conservative' | 'moderate' | 'aggressive' | null;
  autoTrading: boolean;
  notifications: {
    trades: boolean;
    rewards: boolean;
    governance: boolean;
    marketing: boolean;
  };
  referralCode: string;
  agreedToTerms: boolean;
  completedSteps: string[];
}

// =============================================================================
// STEP COMPONENTS
// =============================================================================

function WelcomeStep({ onNext }: StepProps) {
  return (
    <div className="text-center space-y-8 py-8">
      <div className="w-24 h-24 mx-auto bg-gradient-to-br from-purple-500 to-blue-500 rounded-full flex items-center justify-center">
        <Sparkles className="h-12 w-12 text-white" />
      </div>

      <div>
        <h1 className="text-4xl font-bold mb-4">Welcome to JARVIS</h1>
        <p className="text-xl text-muted-foreground max-w-md mx-auto">
          Your autonomous AI trading companion that works 24/7 to help you succeed in crypto.
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 max-w-2xl mx-auto">
        <div className="p-4 bg-muted rounded-lg">
          <Brain className="h-8 w-8 mx-auto mb-2 text-purple-500" />
          <h3 className="font-semibold">AI-Powered</h3>
          <p className="text-sm text-muted-foreground">
            Smart trading decisions based on market analysis
          </p>
        </div>
        <div className="p-4 bg-muted rounded-lg">
          <Shield className="h-8 w-8 mx-auto mb-2 text-green-500" />
          <h3 className="font-semibold">Secure</h3>
          <p className="text-sm text-muted-foreground">
            Your keys, your crypto - always in control
          </p>
        </div>
        <div className="p-4 bg-muted rounded-lg">
          <TrendingUp className="h-8 w-8 mx-auto mb-2 text-blue-500" />
          <h3 className="font-semibold">Earn Rewards</h3>
          <p className="text-sm text-muted-foreground">
            Stake to earn and participate in governance
          </p>
        </div>
      </div>

      <Button size="lg" onClick={onNext} className="px-8">
        Get Started
        <ArrowRight className="ml-2 h-5 w-5" />
      </Button>
    </div>
  );
}

function ConnectWalletStep({ data, updateData, onNext }: StepProps) {
  const [isConnecting, setIsConnecting] = useState(false);
  const [walletType, setWalletType] = useState<string>('');

  const walletOptions = [
    { id: 'phantom', name: 'Phantom', icon: '👻', popular: true },
    { id: 'solflare', name: 'Solflare', icon: '🔆', popular: true },
    { id: 'backpack', name: 'Backpack', icon: '🎒', popular: false },
    { id: 'ledger', name: 'Ledger', icon: '🔐', popular: false }
  ];

  const connectWallet = async (type: string) => {
    setIsConnecting(true);
    setWalletType(type);

    try {
      // Simulate wallet connection
      await new Promise(resolve => setTimeout(resolve, 1500));

      // In production, use actual wallet adapter
      const mockWallet = 'J4RV15' + Math.random().toString(36).substring(2, 8).toUpperCase();
      updateData({ wallet: mockWallet });
      onNext();
    } catch (error) {
      console.error('Failed to connect:', error);
    } finally {
      setIsConnecting(false);
    }
  };

  return (
    <div className="space-y-6">
      <div className="text-center mb-8">
        <div className="w-16 h-16 mx-auto bg-primary/10 rounded-full flex items-center justify-center mb-4">
          <Wallet className="h-8 w-8 text-primary" />
        </div>
        <h2 className="text-2xl font-bold">Connect Your Wallet</h2>
        <p className="text-muted-foreground mt-2">
          Choose your preferred Solana wallet to get started
        </p>
      </div>

      <div className="grid gap-3 max-w-md mx-auto">
        {walletOptions.map(wallet => (
          <Button
            key={wallet.id}
            variant="outline"
            className="h-16 justify-between"
            disabled={isConnecting}
            onClick={() => connectWallet(wallet.id)}
          >
            <div className="flex items-center gap-3">
              <span className="text-2xl">{wallet.icon}</span>
              <span className="font-medium">{wallet.name}</span>
              {wallet.popular && (
                <Badge variant="secondary" className="text-xs">Popular</Badge>
              )}
            </div>
            {isConnecting && walletType === wallet.id ? (
              <span className="animate-pulse">Connecting...</span>
            ) : (
              <ChevronRight className="h-5 w-5 text-muted-foreground" />
            )}
          </Button>
        ))}
      </div>

      <div className="text-center text-sm text-muted-foreground mt-8">
        <p>Don't have a wallet?</p>
        <a
          href="https://phantom.app"
          target="_blank"
          rel="noopener noreferrer"
          className="text-primary hover:underline inline-flex items-center gap-1"
        >
          Create one with Phantom
          <ExternalLink className="h-3 w-3" />
        </a>
      </div>
    </div>
  );
}

function ExperienceStep({ data, updateData, onNext, onBack }: StepProps) {
  const experiences = [
    {
      id: 'beginner',
      title: 'Beginner',
      description: 'New to crypto trading',
      icon: '🌱',
      features: ['Guided tutorials', 'Safety rails enabled', 'Conservative defaults']
    },
    {
      id: 'intermediate',
      title: 'Intermediate',
      description: 'Some trading experience',
      icon: '📈',
      features: ['Moderate suggestions', 'More control options', 'Strategy recommendations']
    },
    {
      id: 'advanced',
      title: 'Advanced',
      description: 'Experienced trader',
      icon: '🚀',
      features: ['Full feature access', 'Custom strategies', 'Advanced analytics']
    }
  ];

  return (
    <div className="space-y-6">
      <div className="text-center mb-8">
        <h2 className="text-2xl font-bold">Your Experience Level</h2>
        <p className="text-muted-foreground mt-2">
          This helps us customize your experience
        </p>
      </div>

      <div className="grid gap-4 max-w-xl mx-auto">
        {experiences.map(exp => (
          <Card
            key={exp.id}
            className={`cursor-pointer transition-all ${
              data.experience === exp.id
                ? 'border-primary ring-2 ring-primary/20'
                : 'hover:border-primary/50'
            }`}
            onClick={() => updateData({ experience: exp.id as any })}
          >
            <CardContent className="p-4">
              <div className="flex items-start gap-4">
                <span className="text-3xl">{exp.icon}</span>
                <div className="flex-1">
                  <div className="flex items-center justify-between">
                    <h3 className="font-semibold">{exp.title}</h3>
                    {data.experience === exp.id && (
                      <Check className="h-5 w-5 text-primary" />
                    )}
                  </div>
                  <p className="text-sm text-muted-foreground">{exp.description}</p>
                  <div className="flex flex-wrap gap-2 mt-2">
                    {exp.features.map(feature => (
                      <Badge key={feature} variant="secondary" className="text-xs">
                        {feature}
                      </Badge>
                    ))}
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      <div className="flex justify-between max-w-xl mx-auto pt-4">
        <Button variant="outline" onClick={onBack}>
          <ArrowLeft className="mr-2 h-4 w-4" />
          Back
        </Button>
        <Button onClick={onNext} disabled={!data.experience}>
          Continue
          <ArrowRight className="ml-2 h-4 w-4" />
        </Button>
      </div>
    </div>
  );
}

function InterestsStep({ data, updateData, onNext, onBack }: StepProps) {
  const interests = [
    { id: 'trading', label: 'Automated Trading', icon: '📊', description: 'AI-powered trade execution' },
    { id: 'staking', label: 'Staking Rewards', icon: '💰', description: 'Earn passive income' },
    { id: 'defi', label: 'DeFi Strategies', icon: '🏦', description: 'Yield farming & liquidity' },
    { id: 'governance', label: 'Governance', icon: '🗳️', description: 'Vote on protocol decisions' },
    { id: 'nft', label: 'NFT Trading', icon: '🖼️', description: 'Coming soon' },
    { id: 'analytics', label: 'Analytics', icon: '📈', description: 'Portfolio insights' }
  ];

  const toggleInterest = (id: string) => {
    const current = data.interests || [];
    const updated = current.includes(id)
      ? current.filter(i => i !== id)
      : [...current, id];
    updateData({ interests: updated });
  };

  return (
    <div className="space-y-6">
      <div className="text-center mb-8">
        <h2 className="text-2xl font-bold">What interests you?</h2>
        <p className="text-muted-foreground mt-2">
          Select all that apply - you can change these later
        </p>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-3 gap-4 max-w-2xl mx-auto">
        {interests.map(interest => (
          <Card
            key={interest.id}
            className={`cursor-pointer transition-all ${
              data.interests?.includes(interest.id)
                ? 'border-primary bg-primary/5'
                : 'hover:border-primary/50'
            }`}
            onClick={() => toggleInterest(interest.id)}
          >
            <CardContent className="p-4 text-center">
              <span className="text-3xl block mb-2">{interest.icon}</span>
              <h3 className="font-semibold text-sm">{interest.label}</h3>
              <p className="text-xs text-muted-foreground mt-1">
                {interest.description}
              </p>
              {data.interests?.includes(interest.id) && (
                <CheckCircle2 className="h-5 w-5 text-primary mx-auto mt-2" />
              )}
            </CardContent>
          </Card>
        ))}
      </div>

      <div className="flex justify-between max-w-2xl mx-auto pt-4">
        <Button variant="outline" onClick={onBack}>
          <ArrowLeft className="mr-2 h-4 w-4" />
          Back
        </Button>
        <Button onClick={onNext} disabled={!data.interests?.length}>
          Continue
          <ArrowRight className="ml-2 h-4 w-4" />
        </Button>
      </div>
    </div>
  );
}

function RiskProfileStep({ data, updateData, onNext, onBack }: StepProps) {
  const profiles = [
    {
      id: 'conservative',
      title: 'Conservative',
      icon: '🛡️',
      description: 'Prioritize capital preservation',
      traits: [
        'Lower volatility exposure',
        'Stablecoin focused',
        'Gradual position building'
      ],
      color: 'text-green-600'
    },
    {
      id: 'moderate',
      title: 'Moderate',
      icon: '⚖️',
      description: 'Balance of growth and safety',
      traits: [
        'Diversified portfolio',
        'Mix of stable and growth',
        'Measured risk-taking'
      ],
      color: 'text-blue-600'
    },
    {
      id: 'aggressive',
      title: 'Aggressive',
      icon: '🔥',
      description: 'Maximize growth potential',
      traits: [
        'Higher volatility tolerance',
        'Growth-focused allocation',
        'Active trading strategies'
      ],
      color: 'text-orange-600'
    }
  ];

  return (
    <div className="space-y-6">
      <div className="text-center mb-8">
        <h2 className="text-2xl font-bold">Risk Profile</h2>
        <p className="text-muted-foreground mt-2">
          Help JARVIS understand your risk tolerance
        </p>
      </div>

      <div className="grid gap-4 max-w-xl mx-auto">
        {profiles.map(profile => (
          <Card
            key={profile.id}
            className={`cursor-pointer transition-all ${
              data.riskTolerance === profile.id
                ? 'border-primary ring-2 ring-primary/20'
                : 'hover:border-primary/50'
            }`}
            onClick={() => updateData({ riskTolerance: profile.id as any })}
          >
            <CardContent className="p-4">
              <div className="flex items-start gap-4">
                <span className="text-3xl">{profile.icon}</span>
                <div className="flex-1">
                  <div className="flex items-center justify-between">
                    <h3 className={`font-semibold ${profile.color}`}>
                      {profile.title}
                    </h3>
                    {data.riskTolerance === profile.id && (
                      <Check className="h-5 w-5 text-primary" />
                    )}
                  </div>
                  <p className="text-sm text-muted-foreground">{profile.description}</p>
                  <ul className="mt-2 space-y-1">
                    {profile.traits.map(trait => (
                      <li key={trait} className="text-xs text-muted-foreground flex items-center gap-2">
                        <Check className="h-3 w-3" />
                        {trait}
                      </li>
                    ))}
                  </ul>
                </div>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      <div className="flex justify-between max-w-xl mx-auto pt-4">
        <Button variant="outline" onClick={onBack}>
          <ArrowLeft className="mr-2 h-4 w-4" />
          Back
        </Button>
        <Button onClick={onNext} disabled={!data.riskTolerance}>
          Continue
          <ArrowRight className="ml-2 h-4 w-4" />
        </Button>
      </div>
    </div>
  );
}

function NotificationsStep({ data, updateData, onNext, onBack }: StepProps) {
  const notifications = data.notifications || {
    trades: true,
    rewards: true,
    governance: false,
    marketing: false
  };

  const updateNotification = (key: string, value: boolean) => {
    updateData({
      notifications: {
        ...notifications,
        [key]: value
      }
    });
  };

  return (
    <div className="space-y-6">
      <div className="text-center mb-8">
        <h2 className="text-2xl font-bold">Notification Preferences</h2>
        <p className="text-muted-foreground mt-2">
          Choose what updates you'd like to receive
        </p>
      </div>

      <div className="space-y-4 max-w-md mx-auto">
        <div className="flex items-center justify-between p-4 border rounded-lg">
          <div className="flex items-center gap-3">
            <Zap className="h-5 w-5 text-yellow-500" />
            <div>
              <p className="font-medium">Trade Alerts</p>
              <p className="text-sm text-muted-foreground">
                Get notified about trade executions
              </p>
            </div>
          </div>
          <Checkbox
            checked={notifications.trades}
            onCheckedChange={(v) => updateNotification('trades', !!v)}
          />
        </div>

        <div className="flex items-center justify-between p-4 border rounded-lg">
          <div className="flex items-center gap-3">
            <Coins className="h-5 w-5 text-green-500" />
            <div>
              <p className="font-medium">Reward Updates</p>
              <p className="text-sm text-muted-foreground">
                Staking rewards and earnings
              </p>
            </div>
          </div>
          <Checkbox
            checked={notifications.rewards}
            onCheckedChange={(v) => updateNotification('rewards', !!v)}
          />
        </div>

        <div className="flex items-center justify-between p-4 border rounded-lg">
          <div className="flex items-center gap-3">
            <Shield className="h-5 w-5 text-purple-500" />
            <div>
              <p className="font-medium">Governance</p>
              <p className="text-sm text-muted-foreground">
                New proposals and voting reminders
              </p>
            </div>
          </div>
          <Checkbox
            checked={notifications.governance}
            onCheckedChange={(v) => updateNotification('governance', !!v)}
          />
        </div>

        <div className="flex items-center justify-between p-4 border rounded-lg">
          <div className="flex items-center gap-3">
            <Gift className="h-5 w-5 text-pink-500" />
            <div>
              <p className="font-medium">News & Updates</p>
              <p className="text-sm text-muted-foreground">
                Product updates and features
              </p>
            </div>
          </div>
          <Checkbox
            checked={notifications.marketing}
            onCheckedChange={(v) => updateNotification('marketing', !!v)}
          />
        </div>
      </div>

      <div className="flex justify-between max-w-md mx-auto pt-4">
        <Button variant="outline" onClick={onBack}>
          <ArrowLeft className="mr-2 h-4 w-4" />
          Back
        </Button>
        <Button onClick={onNext}>
          Continue
          <ArrowRight className="ml-2 h-4 w-4" />
        </Button>
      </div>
    </div>
  );
}

function CompleteStep({ data, onNext }: StepProps) {
  const [copied, setCopied] = useState(false);
  const referralLink = `https://jarvis.ai/ref/${data.wallet?.slice(0, 8)}`;

  const copyReferral = () => {
    navigator.clipboard.writeText(referralLink);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="text-center space-y-8 py-8">
      <div className="w-24 h-24 mx-auto bg-gradient-to-br from-green-400 to-green-600 rounded-full flex items-center justify-center">
        <Check className="h-12 w-12 text-white" />
      </div>

      <div>
        <h1 className="text-4xl font-bold mb-4">You're All Set!</h1>
        <p className="text-xl text-muted-foreground max-w-md mx-auto">
          Welcome to JARVIS. Let's start building your portfolio.
        </p>
      </div>

      {/* Referral Card */}
      <Card className="max-w-md mx-auto">
        <CardHeader>
          <CardTitle className="flex items-center gap-2 justify-center">
            <Gift className="h-5 w-5 text-pink-500" />
            Share & Earn
          </CardTitle>
          <CardDescription>
            Invite friends and earn 10% of their trading fees
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="flex items-center gap-2">
            <Input value={referralLink} readOnly className="text-sm" />
            <Button variant="outline" size="icon" onClick={copyReferral}>
              {copied ? <Check className="h-4 w-4" /> : <Copy className="h-4 w-4" />}
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Next Steps */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 max-w-2xl mx-auto">
        <Card className="cursor-pointer hover:border-primary/50">
          <CardContent className="p-4 text-center">
            <Coins className="h-8 w-8 mx-auto mb-2 text-green-500" />
            <h3 className="font-semibold">Stake Tokens</h3>
            <p className="text-sm text-muted-foreground">
              Earn up to 25% APY
            </p>
          </CardContent>
        </Card>

        <Card className="cursor-pointer hover:border-primary/50">
          <CardContent className="p-4 text-center">
            <TrendingUp className="h-8 w-8 mx-auto mb-2 text-blue-500" />
            <h3 className="font-semibold">Start Trading</h3>
            <p className="text-sm text-muted-foreground">
              AI-powered swaps
            </p>
          </CardContent>
        </Card>

        <Card className="cursor-pointer hover:border-primary/50">
          <CardContent className="p-4 text-center">
            <Brain className="h-8 w-8 mx-auto mb-2 text-purple-500" />
            <h3 className="font-semibold">Explore AI</h3>
            <p className="text-sm text-muted-foreground">
              Set up automations
            </p>
          </CardContent>
        </Card>
      </div>

      <Button size="lg" onClick={onNext} className="px-8">
        <Rocket className="mr-2 h-5 w-5" />
        Launch Dashboard
      </Button>
    </div>
  );
}

// =============================================================================
// STEPS CONFIGURATION
// =============================================================================

const ONBOARDING_STEPS: OnboardingStep[] = [
  { id: 'welcome', title: 'Welcome', description: 'Introduction', icon: Sparkles, component: WelcomeStep },
  { id: 'wallet', title: 'Connect Wallet', description: 'Link your wallet', icon: Wallet, component: ConnectWalletStep },
  { id: 'experience', title: 'Experience', description: 'Your level', icon: TrendingUp, component: ExperienceStep },
  { id: 'interests', title: 'Interests', description: 'What you want', icon: Brain, component: InterestsStep },
  { id: 'risk', title: 'Risk Profile', description: 'Your tolerance', icon: Shield, component: RiskProfileStep },
  { id: 'notifications', title: 'Notifications', description: 'Stay updated', icon: Zap, component: NotificationsStep },
  { id: 'complete', title: 'Complete', description: 'All done!', icon: Check, component: CompleteStep }
];

// =============================================================================
// MAIN COMPONENT
// =============================================================================

interface OnboardingFlowProps {
  onComplete: (data: OnboardingData) => void;
}

export function OnboardingFlow({ onComplete }: OnboardingFlowProps) {
  const [currentStep, setCurrentStep] = useState(0);
  const [data, setData] = useState<OnboardingData>({
    wallet: null,
    experience: null,
    interests: [],
    riskTolerance: null,
    autoTrading: false,
    notifications: {
      trades: true,
      rewards: true,
      governance: false,
      marketing: false
    },
    referralCode: '',
    agreedToTerms: false,
    completedSteps: []
  });

  const updateData = useCallback((updates: Partial<OnboardingData>) => {
    setData(prev => ({ ...prev, ...updates }));
  }, []);

  const goNext = useCallback(() => {
    if (currentStep < ONBOARDING_STEPS.length - 1) {
      setCurrentStep(prev => prev + 1);
    } else {
      onComplete(data);
    }
  }, [currentStep, data, onComplete]);

  const goBack = useCallback(() => {
    if (currentStep > 0) {
      setCurrentStep(prev => prev - 1);
    }
  }, [currentStep]);

  const progress = ((currentStep + 1) / ONBOARDING_STEPS.length) * 100;
  const step = ONBOARDING_STEPS[currentStep];
  const StepComponent = step.component;

  return (
    <div className="min-h-screen bg-background">
      {/* Progress Bar */}
      <div className="fixed top-0 left-0 right-0 z-50 bg-background/95 backdrop-blur border-b">
        <div className="max-w-4xl mx-auto px-4 py-3">
          <div className="flex items-center justify-between mb-2">
            <span className="text-sm font-medium">
              Step {currentStep + 1} of {ONBOARDING_STEPS.length}
            </span>
            <span className="text-sm text-muted-foreground">
              {step.title}
            </span>
          </div>
          <Progress value={progress} className="h-2" />
        </div>
      </div>

      {/* Main Content */}
      <div className="pt-24 pb-12 px-4">
        <div className="max-w-4xl mx-auto">
          <StepComponent
            data={data}
            updateData={updateData}
            onNext={goNext}
            onBack={goBack}
            isFirstStep={currentStep === 0}
            isLastStep={currentStep === ONBOARDING_STEPS.length - 1}
          />
        </div>
      </div>

      {/* Step Indicators */}
      <div className="fixed bottom-0 left-0 right-0 bg-background/95 backdrop-blur border-t">
        <div className="max-w-4xl mx-auto px-4 py-4">
          <div className="flex justify-center gap-2">
            {ONBOARDING_STEPS.map((s, i) => (
              <div
                key={s.id}
                className={`w-2 h-2 rounded-full transition-colors ${
                  i === currentStep
                    ? 'bg-primary'
                    : i < currentStep
                    ? 'bg-primary/50'
                    : 'bg-muted'
                }`}
              />
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

export default OnboardingFlow;
