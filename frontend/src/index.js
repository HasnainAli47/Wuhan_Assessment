/**
 * React Application Entry Point
 * 
 * EXPLANATION FOR VIVA:
 * =====================
 * This is the entry point where React mounts to the DOM.
 * We wrap the App with:
 * - StrictMode: Helps find potential problems
 * - BrowserRouter: Enables client-side routing
 * - AuthProvider: Provides authentication state globally
 */

import React from 'react';
import ReactDOM from 'react-dom/client';
import { BrowserRouter } from 'react-router-dom';
import App from './App';
import { AuthProvider } from './contexts/AuthContext';
import './styles/index.css';

const root = ReactDOM.createRoot(document.getElementById('root'));

root.render(
  <React.StrictMode>
    <BrowserRouter>
      <AuthProvider>
        <App />
      </AuthProvider>
    </BrowserRouter>
  </React.StrictMode>
);
