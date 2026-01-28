/**
 * VersionHistory Component
 * 
 * Slide-out panel showing document version history
 */

import React from 'react';
import { Button } from './Button';
import { Avatar } from './Avatar';
import './VersionHistory.css';

export function VersionHistory({ 
  isOpen, 
  onClose, 
  versions = [],
  onRevert,
  onCompare,
  loading 
}) {
  const formatDate = (dateString) => {
    const date = new Date(dateString);
    return date.toLocaleString('en-US', {
      month: 'short',
      day: 'numeric',
      hour: 'numeric',
      minute: '2-digit'
    });
  };

  return (
    <>
      {isOpen && <div className="version-overlay" onClick={onClose} />}
      <div className={`version-panel ${isOpen ? 'open' : ''}`}>
        <div className="version-header">
          <h3>Version History</h3>
          <button className="version-close" onClick={onClose}>
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M18 6L6 18M6 6l12 12" />
            </svg>
          </button>
        </div>

        <div className="version-content">
          {loading ? (
            <div className="version-loading">
              <div className="loading-spinner" />
              <p>Loading versions...</p>
            </div>
          ) : versions.length === 0 ? (
            <div className="version-empty">
              <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                <circle cx="12" cy="12" r="10" />
                <polyline points="12 6 12 12 16 14" />
              </svg>
              <h4>No versions yet</h4>
              <p>Save a version to track changes over time</p>
            </div>
          ) : (
            <ul className="version-list">
              {versions.map((version, index) => (
                <li key={version.id} className="version-item">
                  <div className="version-marker">
                    <div className="version-dot" />
                    {index < versions.length - 1 && <div className="version-line" />}
                  </div>
                  
                  <div className="version-info">
                    <div className="version-header-row">
                      <span className="version-number">Version {version.version_number}</span>
                      <span className="version-date">{formatDate(version.created_at)}</span>
                    </div>
                    
                    {version.change_summary && (
                      <p className="version-summary">{version.change_summary}</p>
                    )}
                    
                    <div className="version-stats">
                      <span>{version.word_count} words</span>
                      <span>•</span>
                      <span>{version.character_count} chars</span>
                    </div>
                    
                    <div className="version-actions">
                      <Button 
                        variant="secondary" 
                        size="small"
                        onClick={() => onRevert(version.version_number)}
                      >
                        Restore
                      </Button>
                      <Button 
                        variant="ghost" 
                        size="small"
                        onClick={() => onCompare(version.version_number)}
                      >
                        Compare
                      </Button>
                    </div>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
    </>
  );
}

export default VersionHistory;
