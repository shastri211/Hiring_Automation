
import { forwardRef, type ButtonHTMLAttributes } from 'react';
import clsx from 'clsx';

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'secondary' | 'ghost';
  size?: 'md' | 'sm';
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant = 'primary', size = 'md', type = 'button', ...props }, ref) => {
    
    const baseClasses = "inline-flex items-center justify-center gap-2 font-medium rounded-md border border-transparent cursor-pointer transition-base whitespace-nowrap disabled:opacity-60 disabled:cursor-not-allowed";
    
    const sizeClasses = {
      md: "px-4 py-2 text-sm",
      sm: "px-3 py-1 text-xs"
    };

    const variantClasses = {
      primary: "bg-[var(--color-primary-600)] text-white hover:not-disabled:bg-[var(--color-primary-700)] focus-ring",
      secondary: "bg-white border-slate-300 text-slate-900 hover:not-disabled:bg-slate-50 focus-ring",
      ghost: "bg-transparent text-slate-500 hover:not-disabled:bg-slate-100 hover:not-disabled:text-slate-900 focus-ring"
    };

    return (
      <button
        ref={ref}
        type={type}
        className={clsx(
          baseClasses,
          sizeClasses[size],
          variantClasses[variant],
          className
        )}
        {...props}
      />
    );
  }
);

Button.displayName = 'Button';
