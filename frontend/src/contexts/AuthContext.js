/**
 * Authentication Context
 * 
 * EXPLANATION FOR VIVA:
 * =====================
 * React Context provides a way to pass data through the component tree
 * without having to pass props down manually at every level.
 * 
 * Why Context for Auth?
 * 1. Auth state needed everywhere (header, pages, API calls)
 * 2. Avoids "prop drilling" (passing props through many levels)
 * 3. Single source of truth for authentication
 * 
 * This implements the Provider Pattern:
 * - AuthProvider wraps the app
 * - useAuth hook consumes the context
 */

import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';
import { userAPI } from '../services/api';
import { wsService } from '../services/websocket';

// Create the context
const AuthContext = createContext(null);

/**
 * Authentication Provider Component
 * Wraps the application and provides auth state
 */
export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [token, setToken] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  /**
   * Initialize auth state from localStorage
   * This runs once when the app loads
   */
  useEffect(() => {
    const initAuth = async () => {
      const savedToken = localStorage.getItem('authToken');
      const savedUser = localStorage.getItem('currentUser');

      if (savedToken && savedUser) {
        try {
          setToken(savedToken);
          setUser(JSON.parse(savedUser));
          
          // Connect WebSocket
          wsService.connect(savedToken);
          
          // Optionally verify token is still valid
          // await userAPI.getProfile();
        } catch (err) {
          console.error('Failed to restore auth state:', err);
          // Token might be expired, clear it
          localStorage.removeItem('authToken');
          localStorage.removeItem('currentUser');
        }
      }
      
      setLoading(false);
    };

    initAuth();

    // Note: We don't disconnect WebSocket on component unmount because:
    // 1. React 18 Strict Mode causes mount/unmount/mount in development
    // 2. WebSocket should stay connected as long as user is logged in
    // WebSocket is disconnected when user explicitly logs out
  }, []);

  /**
   * Register a new user
   */
  const register = useCallback(async (userData) => {
    setError(null);
    try {
      const response = await userAPI.register(userData);
      return response;
    } catch (err) {
      setError(err.message);
      throw err;
    }
  }, []);

  /**
   * Login user
   */
  const login = useCallback(async (username, password) => {
    setError(null);
    try {
      const response = await userAPI.login(username, password);
      
      const { token: newToken, user: userData } = response;
      
      // Save to state
      setToken(newToken);
      setUser(userData);
      
      // Save to localStorage
      localStorage.setItem('authToken', newToken);
      localStorage.setItem('currentUser', JSON.stringify(userData));
      
      // Connect WebSocket
      wsService.connect(newToken);
      
      return response;
    } catch (err) {
      setError(err.message);
      throw err;
    }
  }, []);

  /**
   * Logout user
   */
  const logout = useCallback(async () => {
    try {
      await userAPI.logout();
    } catch (err) {
      console.error('Logout error:', err);
    } finally {
      // Clear state regardless of API response
      setUser(null);
      setToken(null);
      setError(null);
      
      // Clear localStorage
      localStorage.removeItem('authToken');
      localStorage.removeItem('currentUser');
      
      // Disconnect WebSocket permanently (prevent auto-reconnect)
      wsService.disconnect(true);
    }
  }, []);

  /**
   * Update user profile
   */
  const updateProfile = useCallback(async (updates) => {
    setError(null);
    try {
      const response = await userAPI.updateProfile(updates);
      
      // Update local state
      setUser(response.user);
      localStorage.setItem('currentUser', JSON.stringify(response.user));
      
      return response;
    } catch (err) {
      setError(err.message);
      throw err;
    }
  }, []);

  /**
   * Clear any error
   */
  const clearError = useCallback(() => {
    setError(null);
  }, []);

  // Context value
  const value = {
    user,
    token,
    loading,
    error,
    isAuthenticated: !!user && !!token,
    register,
    login,
    logout,
    updateProfile,
    clearError,
  };

  return (
    <AuthContext.Provider value={value}>
      {children}
    </AuthContext.Provider>
  );
}

/**
 * Custom hook to use auth context
 * 
 * EXPLANATION FOR VIVA:
 * =====================
 * Custom hooks encapsulate reusable logic.
 * This hook provides a clean way to access auth state.
 * 
 * Usage: const { user, login, logout } = useAuth();
 */
export function useAuth() {
  const context = useContext(AuthContext);
  
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  
  return context;
}

export default AuthContext;
