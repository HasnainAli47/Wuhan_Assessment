/**
 * Input Component
 * 
 * EXPLANATION FOR VIVA:
 * =====================
 * Reusable form input with label, error handling, and icons.
 * Demonstrates controlled components in React.
 */

import React, { forwardRef } from 'react';
import './Input.css';

export const Input = forwardRef(({
  label,
  error,
  icon: Icon,
  type = 'text',
  fullWidth = true,
  className = '',
  ...props
}, ref) => {
  const inputId = props.id || props.name || `input-${Math.random().toString(36).substr(2, 9)}`;

  return (
    <div className={`input-wrapper ${fullWidth ? 'input-full' : ''} ${className}`}>
      {label && (
        <label htmlFor={inputId} className="input-label">
          {label}
        </label>
      )}
      <div className={`input-container ${error ? 'input-error' : ''} ${Icon ? 'has-icon' : ''}`}>
        {Icon && (
          <span className="input-icon">
            <Icon size={18} />
          </span>
        )}
        <input
          ref={ref}
          id={inputId}
          type={type}
          className="input-field"
          {...props}
        />
      </div>
      {error && <span className="input-error-message">{error}</span>}
    </div>
  );
});

Input.displayName = 'Input';

export default Input;
