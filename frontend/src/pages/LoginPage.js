/**
 * Login/Register Page
 * 
 * Authentication page with login and register forms.
 * 
 * DEVELOPED BY: Hasnain Ali
 * FOR: Wuhan University Assessment
 * SUPERVISOR: Professor Liang Peng
 * 
 * NOTE FOR ASSESSMENT:
 * - This page demonstrates form handling and validation in React
 * - Email verification is NOT implemented (see notice below)
 * - In a production system, we would integrate SendGrid/Mailgun for OTP verification
 */

import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { Button } from '../components/Button';
import { Input } from '../components/Input';
import { Alert } from '../components/Alert';
import './LoginPage.css';

export function LoginPage() {
  const navigate = useNavigate();
  const { login, register, error, clearError } = useAuth();
  
  const [isLogin, setIsLogin] = useState(true);
  const [loading, setLoading] = useState(false);
  const [success, setSuccess] = useState('');
  
  // Form state
  const [formData, setFormData] = useState({
    username: '',
    email: '',
    password: '',
    displayName: ''
  });

  const handleChange = (e) => {
    const { name, value } = e.target;
    setFormData(prev => ({ ...prev, [name]: value }));
    clearError();
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setSuccess('');

    try {
      if (isLogin) {
        await login(formData.username, formData.password);
        navigate('/');
      } else {
        await register({
          username: formData.username,
          email: formData.email,
          password: formData.password,
          display_name: formData.displayName || null
        });
        setSuccess('Registration successful! You can now sign in.');
        setIsLogin(true);
        setFormData({ username: '', email: '', password: '', displayName: '' });
      }
    } catch (err) {
      // Error is handled by context
    } finally {
      setLoading(false);
    }
  };

  const toggleMode = () => {
    setIsLogin(!isLogin);
    clearError();
    setSuccess('');
    setFormData({ username: '', email: '', password: '', displayName: '' });
  };

  return (
    <div className="login-page">
      <div className="login-container">
        {/* Left side - Branding */}
        <div className="login-branding">
          <div className="branding-content">
            <div className="branding-logo">
              <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M12 19l7-7 3 3-7 7-3-3z" />
                <path d="M18 13l-1.5-7.5L2 2l3.5 14.5L13 18l5-5z" />
                <path d="M2 2l7.586 7.586" />
                <circle cx="11" cy="11" r="2" />
              </svg>
            </div>
            <h1>CollabEdit</h1>
            <p className="branding-tagline">
              Real-time collaborative document editing for teams
            </p>
            <p className="branding-attribution">
              Developed by Hasnain Ali for Wuhan University
            </p>
            
            <div className="branding-features">
              <div className="feature">
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2" />
                  <circle cx="9" cy="7" r="4" />
                  <path d="M23 21v-2a4 4 0 0 0-3-3.87" />
                  <path d="M16 3.13a4 4 0 0 1 0 7.75" />
                </svg>
                <span>Real-time collaboration</span>
              </div>
              <div className="feature">
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <circle cx="12" cy="12" r="10" />
                  <polyline points="12 6 12 12 16 14" />
                </svg>
                <span>Complete version history</span>
              </div>
              <div className="feature">
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <rect x="3" y="11" width="18" height="11" rx="2" ry="2" />
                  <path d="M7 11V7a5 5 0 0 1 10 0v4" />
                </svg>
                <span>Secure & private</span>
              </div>
            </div>
          </div>
        </div>

        {/* Right side - Form */}
        <div className="login-form-container">
          <div className="login-form-wrapper">
            <div className="login-form-header">
              <h2>{isLogin ? 'Welcome back' : 'Create an account'}</h2>
              <p>
                {isLogin 
                  ? 'Sign in to continue to CollabEdit' 
                  : 'Get started with your free account'}
              </p>
            </div>

            {error && (
              <Alert type="error" onClose={clearError}>
                {error}
              </Alert>
            )}

            {success && (
              <Alert type="success">
                {success}
              </Alert>
            )}

            <form onSubmit={handleSubmit} className="login-form">
              <Input
                label={isLogin ? "Username or Email" : "Username"}
                name="username"
                value={formData.username}
                onChange={handleChange}
                placeholder={isLogin ? "Enter username or email" : "Choose a username"}
                required
              />

              {!isLogin && (
                <>
                  <Input
                    label="Email"
                    name="email"
                    type="email"
                    value={formData.email}
                    onChange={handleChange}
                    placeholder="Enter your email"
                    required
                  />
                  <div className="email-notice">
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                      <circle cx="12" cy="12" r="10" />
                      <line x1="12" y1="16" x2="12" y2="12" />
                      <line x1="12" y1="8" x2="12.01" y2="8" />
                    </svg>
                    <span>
                      <strong>Note:</strong> Email verification is not implemented in this assessment. 
                      In production, we would verify emails via OTP using services like SendGrid or Mailgun.
                    </span>
                  </div>
                </>
              )}

              <Input
                label="Password"
                name="password"
                type="password"
                value={formData.password}
                onChange={handleChange}
                placeholder={isLogin ? "Enter your password" : "Create a password (min 6 chars)"}
                required
              />

              {!isLogin && (
                <Input
                  label="Display Name (optional)"
                  name="displayName"
                  value={formData.displayName}
                  onChange={handleChange}
                  placeholder="How should we call you?"
                />
              )}

              <Button 
                type="submit" 
                variant="primary" 
                fullWidth 
                loading={loading}
                className="login-submit"
              >
                {isLogin ? 'Sign In' : 'Create Account'}
              </Button>
            </form>

            <div className="login-footer">
              <p>
                {isLogin ? "Don't have an account? " : "Already have an account? "}
                <button 
                  type="button" 
                  className="login-toggle"
                  onClick={toggleMode}
                >
                  {isLogin ? 'Create one' : 'Sign in'}
                </button>
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

export default LoginPage;
