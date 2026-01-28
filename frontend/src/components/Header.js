/**
 * Header Component
 * 
 * Top navigation bar with logo, actions, and user menu
 */

import React, { useState } from 'react';
import { useAuth } from '../contexts/AuthContext';
import { Avatar } from './Avatar';
import { Button } from './Button';
import './Header.css';

export function Header({ onNewDocument }) {
  const { user, logout } = useAuth();
  const [showUserMenu, setShowUserMenu] = useState(false);

  const handleLogout = async () => {
    await logout();
    setShowUserMenu(false);
  };

  return (
    <header className="header">
      <div className="header-left">
        <div className="header-logo">
          <div className="logo-icon">
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M12 19l7-7 3 3-7 7-3-3z" />
              <path d="M18 13l-1.5-7.5L2 2l3.5 14.5L13 18l5-5z" />
              <path d="M2 2l7.586 7.586" />
              <circle cx="11" cy="11" r="2" />
            </svg>
          </div>
          <span className="logo-text">CollabEdit</span>
        </div>
      </div>

      <div className="header-center">
        <Button variant="primary" onClick={onNewDocument}>
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <line x1="12" y1="5" x2="12" y2="19" />
            <line x1="5" y1="12" x2="19" y2="12" />
          </svg>
          New Document
        </Button>
      </div>

      <div className="header-right">
        <div className="user-menu-container">
          <button 
            className="user-menu-trigger"
            onClick={() => setShowUserMenu(!showUserMenu)}
          >
            <Avatar 
              name={user?.display_name || user?.username} 
              size="medium"
            />
            <span className="user-name">{user?.display_name || user?.username}</span>
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <polyline points="6 9 12 15 18 9" />
            </svg>
          </button>

          {showUserMenu && (
            <>
              <div className="user-menu-overlay" onClick={() => setShowUserMenu(false)} />
              <div className="user-menu">
                <div className="user-menu-header">
                  <Avatar 
                    name={user?.display_name || user?.username} 
                    size="large"
                  />
                  <div className="user-menu-info">
                    <div className="user-menu-name">{user?.display_name || user?.username}</div>
                    <div className="user-menu-email">{user?.email}</div>
                  </div>
                </div>
                <div className="user-menu-divider" />
                <button className="user-menu-item">
                  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" />
                    <circle cx="12" cy="7" r="4" />
                  </svg>
                  Profile Settings
                </button>
                <button className="user-menu-item" onClick={handleLogout}>
                  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" />
                    <polyline points="16 17 21 12 16 7" />
                    <line x1="21" y1="12" x2="9" y2="12" />
                  </svg>
                  Sign Out
                </button>
              </div>
            </>
          )}
        </div>
      </div>
    </header>
  );
}

export default Header;
