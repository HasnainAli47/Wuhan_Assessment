/**
 * Button Component
 * 
 * EXPLANATION FOR VIVA:
 * =====================
 * Reusable button component with multiple variants.
 * Demonstrates React component composition and prop-based styling.
 */

import React from 'react';
import './Button.css';

export function Button({
  children,
  variant = 'primary',
  size = 'medium',
  fullWidth = false,
  disabled = false,
  loading = false,
  icon: Icon,
  onClick,
  type = 'button',
  className = '',
  ...props
}) {
  const classes = [
    'btn',
    `btn-${variant}`,
    `btn-${size}`,
    fullWidth && 'btn-full',
    loading && 'btn-loading',
    className,
  ].filter(Boolean).join(' ');

  return (
    <button
      type={type}
      className={classes}
      disabled={disabled || loading}
      onClick={onClick}
      {...props}
    >
      {loading ? (
        <span className="btn-spinner" />
      ) : (
        <>
          {Icon && <Icon size={size === 'small' ? 14 : 18} />}
          {children}
        </>
      )}
    </button>
  );
}

export default Button;
