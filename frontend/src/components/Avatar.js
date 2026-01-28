/**
 * Avatar Component
 * 
 * Shows user avatar with initials fallback
 */

import React from 'react';
import './Avatar.css';

export function Avatar({ 
  name, 
  src, 
  size = 'medium',
  color,
  className = '' 
}) {
  const getInitials = (name) => {
    if (!name) return '?';
    return name
      .split(' ')
      .map(n => n[0])
      .join('')
      .toUpperCase()
      .slice(0, 2);
  };

  const getColor = (name) => {
    if (color) return color;
    const colors = [
      '#6366f1', '#8b5cf6', '#ec4899', '#ef4444', 
      '#f59e0b', '#10b981', '#06b6d4', '#3b82f6'
    ];
    const index = name ? name.charCodeAt(0) % colors.length : 0;
    return colors[index];
  };

  return (
    <div 
      className={`avatar avatar-${size} ${className}`}
      style={{ backgroundColor: src ? 'transparent' : getColor(name) }}
    >
      {src ? (
        <img src={src} alt={name} className="avatar-image" />
      ) : (
        <span className="avatar-initials">{getInitials(name)}</span>
      )}
    </div>
  );
}

export default Avatar;
