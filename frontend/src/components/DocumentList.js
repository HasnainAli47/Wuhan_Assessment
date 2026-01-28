/**
 * DocumentList Component
 * 
 * Renders list of documents in the sidebar
 */

import React from 'react';
import { Skeleton } from './Loading';
import './DocumentList.css';

export function DocumentList({ 
  documents, 
  selectedId, 
  onSelect, 
  onDelete,
  loading 
}) {
  if (loading) {
    return (
      <div className="document-list-loading">
        {[1, 2, 3].map(i => (
          <div key={i} className="document-item-skeleton">
            <Skeleton width="36px" height="36px" borderRadius="8px" />
            <div style={{ flex: 1 }}>
              <Skeleton width="80%" height="14px" />
              <Skeleton width="50%" height="12px" className="mt-2" />
            </div>
          </div>
        ))}
      </div>
    );
  }

  if (documents.length === 0) {
    return (
      <div className="document-list-empty">
        <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
          <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
          <polyline points="14 2 14 8 20 8" />
          <line x1="12" y1="18" x2="12" y2="12" />
          <line x1="9" y1="15" x2="15" y2="15" />
        </svg>
        <p>No documents yet</p>
        <span>Create your first document to get started</span>
      </div>
    );
  }

  const formatDate = (dateString) => {
    const date = new Date(dateString);
    const now = new Date();
    const diffMs = now - date;
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMs / 3600000);
    const diffDays = Math.floor(diffMs / 86400000);

    if (diffMins < 1) return 'Just now';
    if (diffMins < 60) return `${diffMins}m ago`;
    if (diffHours < 24) return `${diffHours}h ago`;
    if (diffDays < 7) return `${diffDays}d ago`;
    return date.toLocaleDateString();
  };

  return (
    <ul className="document-list">
      {documents.map(doc => (
        <li 
          key={doc.id}
          className={`document-item ${selectedId === doc.id ? 'active' : ''}`}
          onClick={() => onSelect(doc.id)}
        >
          <div className="document-icon">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
              <polyline points="14 2 14 8 20 8" />
              <line x1="16" y1="13" x2="8" y2="13" />
              <line x1="16" y1="17" x2="8" y2="17" />
            </svg>
          </div>
          <div className="document-info">
            <div className="document-title">{doc.title}</div>
            <div className="document-meta">
              {doc.word_count} words • {formatDate(doc.updated_at)}
            </div>
          </div>
          <button 
            className="document-delete"
            onClick={(e) => {
              e.stopPropagation();
              onDelete(doc.id);
            }}
            title="Delete document"
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <polyline points="3 6 5 6 21 6" />
              <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" />
            </svg>
          </button>
        </li>
      ))}
    </ul>
  );
}

export default DocumentList;
