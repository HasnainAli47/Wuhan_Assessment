/**
 * Sidebar Component
 * 
 * DEVELOPED BY: Hasnain Ali
 * FOR: Wuhan University Assessment
 * 
 * Left navigation panel with document list
 */

import React from 'react';
import { DocumentList } from './DocumentList';
import './Sidebar.css';

export function Sidebar({ 
  documents, 
  selectedDocId,
  onSelectDocument,
  onDeleteDocument,
  loading 
}) {
  // Filter to show only user's own documents in "My Documents"
  // Public documents from others will show when selected
  
  return (
    <aside className="sidebar">
      <div className="sidebar-section">
        <h3 className="sidebar-title">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
            <polyline points="14 2 14 8 20 8" />
          </svg>
          My Documents
        </h3>
        <DocumentList 
          documents={documents}
          selectedId={selectedDocId}
          onSelect={onSelectDocument}
          onDelete={onDeleteDocument}
          loading={loading}
        />
      </div>

      <div className="sidebar-footer">
        <div className="sidebar-stats">
          <span className="stat">
            <strong>{documents.length}</strong> document{documents.length !== 1 ? 's' : ''}
          </span>
        </div>
        <div className="sidebar-hint">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <circle cx="12" cy="12" r="10" />
            <line x1="12" y1="16" x2="12" y2="12" />
            <line x1="12" y1="8" x2="12.01" y2="8" />
          </svg>
          <span>Active collaborators shown in editor</span>
        </div>
      </div>
    </aside>
  );
}

export default Sidebar;
