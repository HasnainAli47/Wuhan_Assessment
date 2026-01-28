/**
 * API Service Layer
 * 
 * EXPLANATION FOR VIVA:
 * =====================
 * This module provides a clean abstraction for all backend API calls.
 * 
 * Benefits of separating API logic:
 * 1. Single source of truth for API endpoints
 * 2. Easy to mock for testing
 * 3. Consistent error handling
 * 4. Token management in one place
 * 5. Easy to switch backends or add caching
 * 
 * This follows the Repository Pattern - abstracting data access.
 */

// Use environment variable for API URL in production, fallback to /api for development (proxied)
const API_BASE = process.env.REACT_APP_API_URL || '/api';

/**
 * Get the stored authentication token
 */
const getToken = () => localStorage.getItem('authToken');

/**
 * Generic API request handler
 * Handles authentication headers and error responses
 */
const apiRequest = async (endpoint, options = {}) => {
  const token = getToken();
  
  const config = {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...(token && { Authorization: `Bearer ${token}` }),
      ...options.headers,
    },
  };

  try {
    const response = await fetch(`${API_BASE}${endpoint}`, config);
    const data = await response.json();

    if (!response.ok) {
      // Handle FastAPI/Pydantic validation errors (422)
      // These come as { detail: [{ loc: [...], msg: "...", type: "..." }, ...] }
      let errorMessage = 'Request failed';
      
      if (data.detail) {
        if (Array.isArray(data.detail)) {
          // Pydantic validation error - extract messages
          errorMessage = data.detail
            .map(err => `${err.loc?.slice(-1)[0] || 'Field'}: ${err.msg}`)
            .join(', ');
        } else if (typeof data.detail === 'string') {
          errorMessage = data.detail;
        } else {
          errorMessage = JSON.stringify(data.detail);
        }
      } else if (data.error) {
        errorMessage = data.error;
      }
      
      throw new Error(errorMessage);
    }

    return data;
  } catch (error) {
    console.error(`API Error [${endpoint}]:`, error);
    throw error;
  }
};

// ==================== USER API ====================

export const userAPI = {
  /**
   * Register a new user
   * @param {Object} userData - { username, email, password, display_name? }
   */
  register: (userData) =>
    apiRequest('/users/register', {
      method: 'POST',
      body: JSON.stringify(userData),
    }),

  /**
   * Login user and get JWT token
   * @param {string} username - Username or email
   * @param {string} password - User password
   */
  login: (username, password) =>
    apiRequest('/users/login', {
      method: 'POST',
      body: JSON.stringify({ username, password }),
    }),

  /**
   * Logout current user
   */
  logout: () =>
    apiRequest('/users/logout', {
      method: 'POST',
    }),

  /**
   * Get current user's profile
   */
  getProfile: () => apiRequest('/users/me'),

  /**
   * Update current user's profile
   * @param {Object} updates - Fields to update
   */
  updateProfile: (updates) =>
    apiRequest('/users/me', {
      method: 'PUT',
      body: JSON.stringify(updates),
    }),

  /**
   * Get a user's public profile by ID
   * @param {string} userId - User ID
   */
  getUserById: (userId) => apiRequest(`/users/${userId}`),
};

// ==================== DOCUMENT API ====================

export const documentAPI = {
  /**
   * List all documents accessible to the user
   * @param {Object} options - { include_public, limit, offset }
   */
  list: (options = {}) => {
    const params = new URLSearchParams();
    if (options.include_public) params.append('include_public', 'true');
    if (options.limit) params.append('limit', options.limit);
    if (options.offset) params.append('offset', options.offset);
    
    const query = params.toString();
    return apiRequest(`/documents${query ? `?${query}` : ''}`);
  },

  /**
   * Create a new document
   * @param {Object} documentData - { title, content?, is_public? }
   */
  create: (documentData) =>
    apiRequest('/documents', {
      method: 'POST',
      body: JSON.stringify(documentData),
    }),

  /**
   * Get a document by ID
   * @param {string} documentId - Document ID
   */
  get: (documentId) => apiRequest(`/documents/${documentId}`),

  /**
   * Update a document
   * @param {string} documentId - Document ID
   * @param {Object} updates - { title?, content?, create_version?, change_summary? }
   */
  update: (documentId, updates) =>
    apiRequest(`/documents/${documentId}`, {
      method: 'PUT',
      body: JSON.stringify(updates),
    }),

  /**
   * Delete a document
   * @param {string} documentId - Document ID
   */
  delete: (documentId) =>
    apiRequest(`/documents/${documentId}`, {
      method: 'DELETE',
    }),

  /**
   * Join or leave a collaborative editing session
   * @param {string} documentId - Document ID
   * @param {string} action - 'join', 'leave', or 'update_cursor'
   * @param {number} cursorPosition - Current cursor position
   */
  collaborate: (documentId, action, cursorPosition = 0) =>
    apiRequest(`/documents/${documentId}/collaborate`, {
      method: 'POST',
      body: JSON.stringify({ action, cursor_position: cursorPosition }),
    }),

  /**
   * Track a real-time change
   * @param {string} documentId - Document ID
   * @param {Object} change - { change_type, position, content, length }
   */
  trackChange: (documentId, change) =>
    apiRequest(`/documents/${documentId}/changes`, {
      method: 'POST',
      body: JSON.stringify(change),
    }),
};

// ==================== VERSION API ====================

export const versionAPI = {
  /**
   * Get version history for a document
   * @param {string} documentId - Document ID
   * @param {Object} options - { limit?, include_content? }
   */
  getHistory: (documentId, options = {}) => {
    const params = new URLSearchParams();
    if (options.limit) params.append('limit', options.limit);
    if (options.include_content) params.append('include_content', 'true');
    
    const query = params.toString();
    return apiRequest(`/documents/${documentId}/versions${query ? `?${query}` : ''}`);
  },

  /**
   * Create a new version
   * @param {string} documentId - Document ID
   * @param {string} changeSummary - Description of changes
   */
  create: (documentId, changeSummary = '') =>
    apiRequest(`/documents/${documentId}/versions?change_summary=${encodeURIComponent(changeSummary)}`, {
      method: 'POST',
    }),

  /**
   * Revert to a previous version
   * @param {string} documentId - Document ID
   * @param {Object} options - { version_id? or version_number? }
   */
  revert: (documentId, options) =>
    apiRequest(`/documents/${documentId}/revert`, {
      method: 'POST',
      body: JSON.stringify(options),
    }),

  /**
   * Compare two versions
   * @param {string} documentId - Document ID
   * @param {string} version1 - Version number or 'current'
   * @param {string} version2 - Version number or 'current'
   * @param {string} format - 'unified', 'html', or 'stats'
   */
  compare: (documentId, version1, version2, format = 'stats') =>
    apiRequest(`/documents/${documentId}/compare`, {
      method: 'POST',
      body: JSON.stringify({ version1, version2, format }),
    }),

  /**
   * Get contribution statistics
   * @param {string} documentId - Document ID
   * @param {string} userId - Optional user ID to filter
   */
  getContributions: (documentId, userId = null) => {
    const params = userId ? `?user_id=${userId}` : '';
    return apiRequest(`/documents/${documentId}/contributions${params}`);
  },
};

// ==================== HEALTH API ====================

export const systemAPI = {
  /**
   * Check system health
   */
  health: () => apiRequest('/health'),
};

export default {
  user: userAPI,
  document: documentAPI,
  version: versionAPI,
  system: systemAPI,
};
