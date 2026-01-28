/**
 * Loading Component
 * 
 * Displays loading spinner or skeleton states
 */

import React from 'react';
import './Loading.css';

export function Loading({ 
  size = 'medium',
  fullScreen = false,
  message = '',
  className = ''
}) {
  const spinner = (
    <div className={`loading-container ${className}`}>
      <div className={`loading-spinner loading-${size}`} />
      {message && <p className="loading-message">{message}</p>}
    </div>
  );

  if (fullScreen) {
    return (
      <div className="loading-fullscreen">
        {spinner}
      </div>
    );
  }

  return spinner;
}

// Skeleton loader for content placeholders
export function Skeleton({ 
  width, 
  height, 
  borderRadius = 'var(--radius-md)',
  className = '' 
}) {
  return (
    <div 
      className={`skeleton ${className}`}
      style={{ 
        width, 
        height, 
        borderRadius 
      }}
    />
  );
}

export default Loading;
