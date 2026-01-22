/**
 * GlassCard Component - Premium Glassmorphism Card
 * Matches jarvislife.io design system
 */
import React from 'react';
import clsx from 'clsx';

interface GlassCardProps {
  children: React.ReactNode;
  className?: string;
  glow?: boolean;
  onClick?: () => void;
  hover?: boolean;
}

export const GlassCard: React.FC<GlassCardProps> = ({
  children,
  className,
  glow = false,
  onClick,
  hover = true,
}) => {
  return (
    <div
      className={clsx(
        glow ? 'glass-card-glow' : 'glass-card',
        hover && 'hover:scale-[1.02] cursor-pointer',
        className
      )}
      onClick={onClick}
    >
      {children}
    </div>
  );
};

interface GlassCardHeaderProps {
  children: React.ReactNode;
  className?: string;
}

export const GlassCardHeader: React.FC<GlassCardHeaderProps> = ({
  children,
  className,
}) => {
  return (
    <div className={clsx('border-b border-white/10 pb-4 mb-4', className)}>
      {children}
    </div>
  );
};

interface GlassCardTitleProps {
  children: React.ReactNode;
  className?: string;
  icon?: React.ReactNode;
}

export const GlassCardTitle: React.FC<GlassCardTitleProps> = ({
  children,
  icon,
  className,
}) => {
  return (
    <h3 className={clsx('text-xl font-display font-semibold flex items-center gap-2', className)}>
      {icon && <span className="text-accent">{icon}</span>}
      {children}
    </h3>
  );
};

interface GlassCardBodyProps {
  children: React.ReactNode;
  className?: string;
}

export const GlassCardBody: React.FC<GlassCardBodyProps> = ({
  children,
  className,
}) => {
  return <div className={className}>{children}</div>;
};
