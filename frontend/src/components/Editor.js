/**
 * Editor Component
 * 
 * DEVELOPED BY: Hasnain Ali
 * FOR: Wuhan University Assessment
 * SUPERVISOR: Professor Liang Peng
 * 
 * EXPLANATION FOR VIVA:
 * =====================
 * This is the main text editor component for collaborative editing.
 * 
 * Key Features:
 * - Real-time content sync via WebSocket
 * - Auto-save with debouncing (2 second delay to batch changes)
 * - Word/character count
 * - Version saving (manual snapshots)
 * - Remote cursor display (see other users' cursors)
 * - Conflict detection and resolution (optimistic locking)
 * 
 * DESIGN DECISIONS:
 * - Using textarea for simplicity; production would use contenteditable or ProseMirror
 * - WebSocket for real-time, REST for persistence
 * - Debounced saves to reduce server load
 */

import React, { useState, useEffect, useCallback, useRef } from 'react';
import { Button } from './Button';
import { Input } from './Input';
import { Modal } from './Modal';
import { Avatar } from './Avatar';
import { wsService } from '../services/websocket';
import './Editor.css';

export function Editor({ 
  document,
  onSave,
  onSaveVersion,
  onTitleChange,
  onShowHistory,
  onShowContributions,
  activeEditors = []
}) {
  const [content, setContent] = useState(document?.content || '');
  const [title, setTitle] = useState(document?.title || 'Untitled Document');
  const [isSaving, setIsSaving] = useState(false);
  const [lastSaved, setLastSaved] = useState(null);
  const [showVersionModal, setShowVersionModal] = useState(false);
  const [versionSummary, setVersionSummary] = useState('');
  
  // Remote cursors state: { [userId]: { position, selectionStart, selectionEnd, username, color } }
  const [remoteCursors, setRemoteCursors] = useState({});
  
  // Conflict state
  const [showConflictModal, setShowConflictModal] = useState(false);
  const [conflictData, setConflictData] = useState(null);
  
  const textareaRef = useRef(null);
  const saveTimeoutRef = useRef(null);
  const cursorUpdateTimeoutRef = useRef(null);

  // Sync content when document changes (including after revert)
  useEffect(() => {
    if (document) {
      setContent(document.content || '');
      setTitle(document.title || 'Untitled Document');
    }
  }, [document?.id, document?.content, document?.title]);

  // Auto-save with debouncing
  const debouncedSave = useCallback((newContent) => {
    if (saveTimeoutRef.current) {
      clearTimeout(saveTimeoutRef.current);
    }

    saveTimeoutRef.current = setTimeout(async () => {
      try {
        setIsSaving(true);
        const result = await onSave(newContent);
        
        // Check for conflict
        if (result?.conflict) {
          setConflictData(result);
          setShowConflictModal(true);
        } else {
          setLastSaved(new Date());
        }
      } catch (error) {
        console.error('Auto-save failed:', error);
        // Check if error contains conflict info
        if (error.message?.includes('Conflict')) {
          alert('Your changes conflict with another user\'s edits. Please refresh the document.');
        }
      } finally {
        setIsSaving(false);
      }
    }, 2000);
  }, [onSave]);

  // Handle content change
  const handleContentChange = (e) => {
    const newContent = e.target.value;
    setContent(newContent);
    debouncedSave(newContent);

    // Send change to other users via WebSocket
    if (document?.id) {
      wsService.sendTextChange(document.id, {
        type: 'replace',
        position: 0,
        content: newContent,
        length: content.length
      });
    }
  };
  
  // Handle cursor/selection change
  const handleSelectionChange = useCallback(() => {
    if (!document?.id || !textareaRef.current) return;
    
    // Debounce cursor updates
    if (cursorUpdateTimeoutRef.current) {
      clearTimeout(cursorUpdateTimeoutRef.current);
    }
    
    cursorUpdateTimeoutRef.current = setTimeout(() => {
      const textarea = textareaRef.current;
      const position = textarea.selectionStart;
      const selectionStart = textarea.selectionStart;
      const selectionEnd = textarea.selectionEnd;
      
      wsService.updateCursor(document.id, position, selectionStart, selectionEnd);
    }, 50); // Small delay to batch rapid cursor movements
  }, [document?.id]);

  // Handle title change
  const handleTitleChange = (e) => {
    const newTitle = e.target.value;
    setTitle(newTitle);
  };

  const handleTitleBlur = () => {
    if (title !== document?.title) {
      onTitleChange(title);
    }
  };

  // Track content in a ref to avoid stale closures
  const contentRef = useRef(content);
  useEffect(() => {
    contentRef.current = content;
  }, [content]);

  // Listen for remote changes and cursors
  useEffect(() => {
    if (!document?.id) return;

    // Listen for text changes
    const unsubscribeText = wsService.on('text_change', (data) => {
      if (data.document_id === document.id && data.change) {
        if (data.change.content !== contentRef.current) {
          setContent(data.change.content);
        }
      }
    });
    
    // Listen for cursor updates
    const unsubscribeCursor = wsService.on('cursor_update', (data) => {
      if (data.document_id === document.id) {
        setRemoteCursors(prev => ({
          ...prev,
          [data.user_id]: {
            position: data.position,
            selectionStart: data.selection_start,
            selectionEnd: data.selection_end,
            username: data.username,
            color: data.color
          }
        }));
      }
    });
    
    // Listen for users leaving
    const unsubscribeLeave = wsService.on('user_left', (data) => {
      if (data.document_id === document.id) {
        setRemoteCursors(prev => {
          const newCursors = { ...prev };
          delete newCursors[data.user_id];
          return newCursors;
        });
      }
    });

    return () => {
      unsubscribeText();
      unsubscribeCursor();
      unsubscribeLeave();
    };
  }, [document?.id]); // Removed content dependency - using ref instead

  // Calculate word and character count
  const wordCount = content.trim() ? content.trim().split(/\s+/).length : 0;
  const charCount = content.length;

  // Manual save version - opens modal
  const handleSaveVersionClick = () => {
    setVersionSummary('');
    setShowVersionModal(true);
  };

  // Confirm save version from modal
  const handleSaveVersionConfirm = async () => {
    await onSaveVersion(versionSummary || 'Manual save');
    setShowVersionModal(false);
    setVersionSummary('');
  };
  
  // Handle conflict resolution
  const handleKeepMyChanges = () => {
    // Force save with current content
    onSave(content, true); // true = force save
    setShowConflictModal(false);
    setConflictData(null);
  };
  
  const handleUseServerVersion = () => {
    // Replace content with server version
    if (conflictData?.server_content !== undefined) {
      setContent(conflictData.server_content);
    }
    if (conflictData?.server_title) {
      setTitle(conflictData.server_title);
    }
    setShowConflictModal(false);
    setConflictData(null);
  };
  
  // Get cursor position info for display
  const getCursorPositionInfo = (position) => {
    if (!textareaRef.current) return { line: 1, column: 1 };
    
    const text = content.substring(0, position);
    const lines = text.split('\n');
    return {
      line: lines.length,
      column: lines[lines.length - 1].length + 1
    };
  };

  if (!document) {
    return (
      <div className="editor-empty">
        <div className="editor-empty-icon">
          <svg width="64" height="64" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
            <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
            <polyline points="14 2 14 8 20 8" />
            <line x1="12" y1="18" x2="12" y2="12" />
            <line x1="9" y1="15" x2="15" y2="15" />
          </svg>
        </div>
        <h2>No document selected</h2>
        <p>Select a document from the sidebar or create a new one to start editing</p>
      </div>
    );
  }

  return (
    <div className="editor">
      {/* Editor Header */}
      <div className="editor-header">
        <div className="editor-title-section">
          <input
            type="text"
            value={title}
            onChange={handleTitleChange}
            onBlur={handleTitleBlur}
            className="editor-title-input"
            placeholder="Untitled Document"
          />
          <span className="editor-save-status">
            {isSaving ? (
              <>
                <span className="save-spinner" />
                Saving...
              </>
            ) : lastSaved ? (
              `Saved ${lastSaved.toLocaleTimeString()}`
            ) : (
              'All changes saved'
            )}
          </span>
        </div>

        <div className="editor-actions">
          <Button variant="ghost" size="small" onClick={handleSaveVersionClick}>
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2z" />
              <polyline points="17 21 17 13 7 13 7 21" />
              <polyline points="7 3 7 8 15 8" />
            </svg>
            Save Version
          </Button>
          <Button variant="ghost" size="small" onClick={onShowHistory}>
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <circle cx="12" cy="12" r="10" />
              <polyline points="12 6 12 12 16 14" />
            </svg>
            History
          </Button>
          <Button variant="ghost" size="small" onClick={onShowContributions}>
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2" />
              <circle cx="9" cy="7" r="4" />
              <path d="M23 21v-2a4 4 0 0 0-3-3.87" />
              <path d="M16 3.13a4 4 0 0 1 0 7.75" />
            </svg>
            Contributors
          </Button>
        </div>
      </div>

      {/* Toolbar */}
      <div className="editor-toolbar">
        <div className="toolbar-group">
          <button className="toolbar-btn" title="Bold (Ctrl+B)">
            <strong>B</strong>
          </button>
          <button className="toolbar-btn" title="Italic (Ctrl+I)">
            <em>I</em>
          </button>
          <button className="toolbar-btn" title="Underline (Ctrl+U)">
            <u>U</u>
          </button>
        </div>
        <div className="toolbar-divider" />
        <div className="toolbar-group">
          <button className="toolbar-btn" title="Heading 1">H1</button>
          <button className="toolbar-btn" title="Heading 2">H2</button>
          <button className="toolbar-btn" title="Heading 3">H3</button>
        </div>
        <div className="toolbar-divider" />
        <div className="toolbar-group">
          <button className="toolbar-btn" title="Bullet List">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <line x1="8" y1="6" x2="21" y2="6" />
              <line x1="8" y1="12" x2="21" y2="12" />
              <line x1="8" y1="18" x2="21" y2="18" />
              <line x1="3" y1="6" x2="3.01" y2="6" />
              <line x1="3" y1="12" x2="3.01" y2="12" />
              <line x1="3" y1="18" x2="3.01" y2="18" />
            </svg>
          </button>
          <button className="toolbar-btn" title="Numbered List">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <line x1="10" y1="6" x2="21" y2="6" />
              <line x1="10" y1="12" x2="21" y2="12" />
              <line x1="10" y1="18" x2="21" y2="18" />
              <path d="M4 6h1v4" />
              <path d="M4 10h2" />
              <path d="M6 18H4c0-1 2-2 2-3s-1-1.5-2-1" />
            </svg>
          </button>
        </div>
      </div>

      {/* Editor Body */}
      <div className="editor-body">
        <div className="editor-container-wrapper">
          <textarea
            ref={textareaRef}
            value={content}
            onChange={handleContentChange}
            onSelect={handleSelectionChange}
            onKeyUp={handleSelectionChange}
            onClick={handleSelectionChange}
            className="editor-textarea"
            placeholder="Start typing your document..."
            spellCheck="true"
          />
          
          {/* Remote Cursors Indicator */}
          {Object.keys(remoteCursors).length > 0 && (
            <div className="remote-cursors-indicator">
              {Object.entries(remoteCursors).map(([userId, cursor]) => {
                const posInfo = getCursorPositionInfo(cursor.position);
                return (
                  <div 
                    key={userId}
                    className="remote-cursor-badge"
                    style={{ backgroundColor: cursor.color }}
                    title={`${cursor.username} at line ${posInfo.line}, col ${posInfo.column}`}
                  >
                    <span className="cursor-user-name">{cursor.username}</span>
                    <span className="cursor-position">L{posInfo.line}:C{posInfo.column}</span>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>

      {/* Editor Footer */}
      <div className="editor-footer">
        <div className="editor-stats">
          <span>{wordCount.toLocaleString()} words</span>
          <span className="stat-divider">•</span>
          <span>{charCount.toLocaleString()} characters</span>
        </div>

        {(activeEditors.length > 0 || Object.keys(remoteCursors).length > 0) && (
          <div className="editor-collaborators">
            <span className="collaborators-label">
              <span className="live-indicator" /> Live editing:
            </span>
            <div className="collaborators-avatars">
              {Object.entries(remoteCursors).map(([userId, cursor]) => (
                <div 
                  key={userId}
                  className="collaborator-avatar"
                  style={{ 
                    backgroundColor: cursor.color,
                    border: `2px solid ${cursor.color}`
                  }}
                  title={cursor.username}
                >
                  {cursor.username[0].toUpperCase()}
                </div>
              ))}
              {activeEditors.filter(e => !remoteCursors[e]).slice(0, 5).map((editor, i) => (
                <Avatar 
                  key={editor} 
                  name={editor} 
                  size="small"
                />
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Save Version Modal */}
      <Modal
        isOpen={showVersionModal}
        onClose={() => setShowVersionModal(false)}
        title="Save Version"
      >
        <div className="version-modal-content">
          <p className="version-modal-description">
            Create a named version of this document. This allows you to track changes and revert if needed.
          </p>
          <Input
            label="Version Summary (optional)"
            placeholder="e.g., Added introduction section"
            value={versionSummary}
            onChange={(e) => setVersionSummary(e.target.value)}
          />
          <div className="version-modal-actions">
            <Button variant="ghost" onClick={() => setShowVersionModal(false)}>
              Cancel
            </Button>
            <Button onClick={handleSaveVersionConfirm}>
              Save Version
            </Button>
          </div>
        </div>
      </Modal>
      
      {/* Conflict Resolution Modal */}
      <Modal
        isOpen={showConflictModal}
        onClose={() => setShowConflictModal(false)}
        title="Edit Conflict Detected"
      >
        <div className="conflict-modal-content">
          <div className="conflict-warning">
            <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z" />
              <line x1="12" y1="9" x2="12" y2="13" />
              <line x1="12" y1="17" x2="12.01" y2="17" />
            </svg>
          </div>
          <p className="conflict-description">
            Another user has edited this document since you started editing. 
            You need to choose how to resolve this conflict.
          </p>
          
          <div className="conflict-options">
            <div className="conflict-option">
              <h4>Your Changes</h4>
              <p className="conflict-preview">
                {content.substring(0, 100)}{content.length > 100 ? '...' : ''}
              </p>
              <Button onClick={handleKeepMyChanges}>
                Keep My Changes
              </Button>
            </div>
            
            <div className="conflict-divider">OR</div>
            
            <div className="conflict-option">
              <h4>Server Version</h4>
              <p className="conflict-preview">
                {conflictData?.server_content?.substring(0, 100)}
                {conflictData?.server_content?.length > 100 ? '...' : ''}
              </p>
              <Button variant="secondary" onClick={handleUseServerVersion}>
                Use Server Version
              </Button>
            </div>
          </div>
          
          <p className="conflict-tip">
            <strong>Tip:</strong> You can also copy your text, use the server version, 
            then manually merge your changes.
          </p>
        </div>
      </Modal>
    </div>
  );
}

export default Editor;
