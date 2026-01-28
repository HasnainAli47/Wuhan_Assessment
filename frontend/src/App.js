/**
 * Main Application Component
 * 
 * EXPLANATION FOR VIVA:
 * =====================
 * This is the root component that sets up routing and authentication.
 * 
 * React Router handles client-side navigation:
 * - Routes define which component renders for each URL
 * - Navigate redirects users (e.g., to login if not authenticated)
 * - Protected routes check authentication before rendering
 * 
 * The app structure:
 * - / (Dashboard) - Protected, requires authentication
 * - /login - Public, authentication page
 */

import React from 'react';
import { Routes, Route, Navigate } from 'react-router-dom';
import { useAuth } from './contexts/AuthContext';
import { LoginPage } from './pages/LoginPage';
import { DashboardPage } from './pages/DashboardPage';
import { Loading } from './components/Loading';

/**
 * Protected Route Component
 * 
 * Wraps routes that require authentication.
 * Redirects to login if user is not authenticated.
 */
function ProtectedRoute({ children }) {
  const { isAuthenticated, loading } = useAuth();

  // Show loading while checking auth state
  if (loading) {
    return <Loading fullScreen message="Loading..." />;
  }

  // Redirect to login if not authenticated
  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }

  return children;
}

/**
 * Public Route Component
 * 
 * Wraps routes that should only be accessible when NOT authenticated.
 * Redirects to dashboard if user is already authenticated.
 */
function PublicRoute({ children }) {
  const { isAuthenticated, loading } = useAuth();

  // Show loading while checking auth state
  if (loading) {
    return <Loading fullScreen message="Loading..." />;
  }

  // Redirect to dashboard if already authenticated
  if (isAuthenticated) {
    return <Navigate to="/" replace />;
  }

  return children;
}

/**
 * Main App Component
 */
function App() {
  return (
    <Routes>
      {/* Public routes */}
      <Route 
        path="/login" 
        element={
          <PublicRoute>
            <LoginPage />
          </PublicRoute>
        } 
      />

      {/* Protected routes */}
      <Route 
        path="/" 
        element={
          <ProtectedRoute>
            <DashboardPage />
          </ProtectedRoute>
        } 
      />

      {/* Catch all - redirect to home */}
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}

export default App;
