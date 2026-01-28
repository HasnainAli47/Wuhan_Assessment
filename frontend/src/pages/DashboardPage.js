/**
 * Dashboard Page
 * 
 * Main application page with sidebar, editor, and panels
 */

import React, { useState, useEffect, useCallback } from 'react';
import { useAuth } from '../contexts/AuthContext';
import { documentAPI, versionAPI } from '../services/api';
import { wsService } from '../services/websocket';
import { Header } from '../components/Header';
import { Sidebar } from '../components/Sidebar';
import { Editor } from '../components/Editor';
import { VersionHistory } from '../components/VersionHistory';
import { Modal } from '../components/Modal';
import { Button } from '../components/Button';
import { Input } from '../components/Input';
import { Alert } from '../components/Alert';
import './DashboardPage.css';

export function DashboardPage() {
  const { user } = useAuth();
  
  // Document state
  const [documents, setDocuments] = useState([]);
  const [selectedDoc, setSelectedDoc] = useState(null);
  const [loading, setLoading] = useState(true);
  
  // Panel state
  const [showHistory, setShowHistory] = useState(false);
  const [versions, setVersions] = useState([]);
  const [versionsLoading, setVersionsLoading] = useState(false);
  
  // Modal state
  const [showNewDocModal, setShowNewDocModal] = useState(false);
  const [showContribModal, setShowContribModal] = useState(false);
  const [contributions, setContributions] = useState([]);
  
  // New document form
  const [newDocTitle, setNewDocTitle] = useState('');
  const [newDocPublic, setNewDocPublic] = useState(false);
  const [creating, setCreating] = useState(false);
  
  // Error state
  const [error, setError] = useState(null);

  // Load documents on mount
  useEffect(() => {
    loadDocuments();
  }, []);

  // WebSocket setup for real-time updates
  useEffect(() => {
    const unsubscribeJoined = wsService.on('user_joined', (data) => {
      console.log('User joined:', data);
    });

    const unsubscribeLeft = wsService.on('user_left', (data) => {
      console.log('User left:', data);
    });

    return () => {
      unsubscribeJoined();
      unsubscribeLeft();
    };
  }, []);

  // Join/leave document room when selection changes
  useEffect(() => {
    if (selectedDoc?.id) {
      wsService.joinDocument(selectedDoc.id);
      return () => wsService.leaveDocument(selectedDoc.id);
    }
  }, [selectedDoc?.id]);

  const loadDocuments = async () => {
    try {
      setLoading(true);
      const response = await documentAPI.list({ include_public: true });
      setDocuments(response.documents || []);
    } catch (err) {
      setError('Failed to load documents');
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const selectDocument = async (docId) => {
    try {
      const response = await documentAPI.get(docId);
      setSelectedDoc(response.document);
    } catch (err) {
      setError('Failed to load document');
      console.error(err);
    }
  };

  const createDocument = async () => {
    if (!newDocTitle.trim()) return;

    try {
      setCreating(true);
      const response = await documentAPI.create({
        title: newDocTitle.trim(),
        content: '',
        is_public: newDocPublic
      });
      
      setDocuments(prev => [response.document, ...prev]);
      setSelectedDoc(response.document);
      setShowNewDocModal(false);
      setNewDocTitle('');
      setNewDocPublic(false);
    } catch (err) {
      // Check if it's an auth issue
      if (err.message && (err.message.includes('User not found') || err.message.includes('log in'))) {
        alert('Session expired. Please log out and log in again.');
      } else {
        setError('Failed to create document: ' + err.message);
      }
      console.error(err);
    } finally {
      setCreating(false);
    }
  };

  const deleteDocument = async (docId) => {
    if (!window.confirm('Are you sure you want to delete this document?')) {
      return;
    }

    try {
      await documentAPI.delete(docId);
      setDocuments(prev => prev.filter(d => d.id !== docId));
      if (selectedDoc?.id === docId) {
        setSelectedDoc(null);
      }
    } catch (err) {
      setError('Failed to delete document');
      console.error(err);
    }
  };

  const saveDocument = useCallback(async (content, forceOverwrite = false) => {
    if (!selectedDoc) return;

    try {
      // Pass expected_version for conflict detection (unless forcing overwrite)
      const updateData = { 
        content,
        expected_version: forceOverwrite ? undefined : selectedDoc.edit_version
      };
      
      const response = await documentAPI.update(selectedDoc.id, updateData);
      
      // Update local state with new version number
      const newDoc = response.document || { ...selectedDoc, content };
      setSelectedDoc(prev => ({ 
        ...prev, 
        content,
        edit_version: newDoc.edit_version || (prev.edit_version || 1) + 1
      }));
      setDocuments(prev => 
        prev.map(d => d.id === selectedDoc.id 
          ? { ...d, word_count: content.split(/\s+/).filter(Boolean).length }
          : d
        )
      );
      
      return response;
    } catch (err) {
      // Check if it's a conflict error
      if (err.message?.includes('Conflict')) {
        // Return conflict info for the Editor to handle
        return {
          conflict: true,
          error: err.message,
          server_content: selectedDoc.content // This would need to be fetched fresh
        };
      }
      setError('Failed to save document');
      throw err;
    }
  }, [selectedDoc]);

  const saveTitle = useCallback(async (title) => {
    if (!selectedDoc) return;

    try {
      await documentAPI.update(selectedDoc.id, { title });
      
      setSelectedDoc(prev => ({ ...prev, title }));
      setDocuments(prev =>
        prev.map(d => d.id === selectedDoc.id ? { ...d, title } : d)
      );
    } catch (err) {
      setError('Failed to update title');
      console.error(err);
    }
  }, [selectedDoc]);

  const saveVersion = useCallback(async (summary) => {
    if (!selectedDoc) return;

    try {
      await versionAPI.create(selectedDoc.id, summary);
      setError(null);
      
      // Show success message
      alert('Version saved successfully!');
      
      // Reload versions if panel is open
      if (showHistory) {
        loadVersions();
      }
    } catch (err) {
      // Check if it's a "no changes" error
      if (err.message && err.message.toLowerCase().includes('no changes')) {
        alert('No changes detected. The content is identical to the latest version.');
      } else {
        setError('Failed to save version');
        alert('Failed to save version: ' + err.message);
      }
      console.error(err);
    }
  }, [selectedDoc, showHistory]);

  const loadVersions = async () => {
    if (!selectedDoc) return;

    try {
      setVersionsLoading(true);
      const response = await versionAPI.getHistory(selectedDoc.id);
      setVersions(response.versions || []);
    } catch (err) {
      console.error('Failed to load versions:', err);
    } finally {
      setVersionsLoading(false);
    }
  };

  const handleShowHistory = () => {
    setShowHistory(true);
    loadVersions();
  };

  const handleRevert = async (versionNumber) => {
    if (!window.confirm(`Revert to version ${versionNumber}? This will replace current content.`)) {
      return;
    }

    try {
      const response = await versionAPI.revert(selectedDoc.id, { 
        version_number: versionNumber 
      });
      
      setSelectedDoc(response.document);
      loadVersions();
    } catch (err) {
      setError('Failed to revert version');
      console.error(err);
    }
  };

  const handleCompare = async (versionNumber) => {
    try {
      const response = await versionAPI.compare(
        selectedDoc.id, 
        versionNumber.toString(), 
        'current',
        'stats'
      );
      
      const stats = response.diff.statistics;
      alert(
        `Comparison: Version ${versionNumber} vs Current\n\n` +
        `Similarity: ${stats.similarity}%\n` +
        `Characters added: ${stats.characters_added}\n` +
        `Characters removed: ${stats.characters_removed}`
      );
    } catch (err) {
      setError('Failed to compare versions');
      console.error(err);
    }
  };

  const handleShowContributions = async () => {
    if (!selectedDoc) return;

    try {
      const response = await versionAPI.getContributions(selectedDoc.id);
      setContributions(response.contributions || []);
      setShowContribModal(true);
    } catch (err) {
      console.error('Failed to load contributions:', err);
    }
  };

  return (
    <div className="dashboard">
      <Header onNewDocument={() => setShowNewDocModal(true)} />
      
      <div className="dashboard-content">
        <Sidebar
          documents={documents}
          selectedDocId={selectedDoc?.id}
          onSelectDocument={selectDocument}
          onDeleteDocument={deleteDocument}
          loading={loading}
        />
        
        <main className="dashboard-main">
          {error && (
            <Alert type="error" onClose={() => setError(null)} className="dashboard-alert">
              {error}
            </Alert>
          )}
          
          <Editor
            document={selectedDoc}
            onSave={saveDocument}
            onSaveVersion={saveVersion}
            onTitleChange={saveTitle}
            onShowHistory={handleShowHistory}
            onShowContributions={handleShowContributions}
          />
        </main>
      </div>

      {/* Version History Panel */}
      <VersionHistory
        isOpen={showHistory}
        onClose={() => setShowHistory(false)}
        versions={versions}
        onRevert={handleRevert}
        onCompare={handleCompare}
        loading={versionsLoading}
      />

      {/* New Document Modal */}
      <Modal
        isOpen={showNewDocModal}
        onClose={() => setShowNewDocModal(false)}
        title="Create New Document"
        footer={
          <>
            <Button variant="secondary" onClick={() => setShowNewDocModal(false)}>
              Cancel
            </Button>
            <Button variant="primary" onClick={createDocument} loading={creating}>
              Create Document
            </Button>
          </>
        }
      >
        <div className="new-doc-form">
          <Input
            label="Document Title"
            value={newDocTitle}
            onChange={(e) => setNewDocTitle(e.target.value)}
            placeholder="Enter document title"
            autoFocus
          />
          <label className="checkbox-label">
            <input
              type="checkbox"
              checked={newDocPublic}
              onChange={(e) => setNewDocPublic(e.target.checked)}
            />
            <span>Make this document public</span>
          </label>
        </div>
      </Modal>

      {/* Contributions Modal */}
      <Modal
        isOpen={showContribModal}
        onClose={() => setShowContribModal(false)}
        title="Document Contributors"
        size="large"
      >
        <div className="contributions-list">
          {contributions.length === 0 ? (
            <p className="text-muted text-center">No contributions recorded yet</p>
          ) : (
            contributions.map(contrib => (
              <div key={contrib.user_id} className="contribution-item">
                <div className="contribution-user">
                  <div 
                    className="contribution-avatar"
                    style={{ backgroundColor: `hsl(${(contrib.user_id || '').charCodeAt(0) * 10}, 70%, 50%)` }}
                  >
                    {(contrib.display_name || contrib.username || 'U')[0].toUpperCase()}
                  </div>
                  <div className="contribution-info">
                    <div className="contribution-name">
                      {contrib.display_name || contrib.username || 'Unknown User'}
                      {contrib.is_owner && <span className="owner-badge">Owner</span>}
                    </div>
                    <div className="contribution-stats">
                      {contrib.versions_created > 0 && (
                        <span>{contrib.versions_created} version{contrib.versions_created !== 1 ? 's' : ''} • </span>
                      )}
                      {contrib.total_changes > 0 && (
                        <span>{contrib.total_changes} edit{contrib.total_changes !== 1 ? 's' : ''} • </span>
                      )}
                      {(contrib.characters_added > 0 || contrib.characters_removed > 0) && (
                        <span>+{contrib.characters_added || 0} / -{contrib.characters_removed || 0} chars</span>
                      )}
                      {contrib.total_changes === 0 && contrib.versions_created === 0 && (
                        <span>Document creator</span>
                      )}
                    </div>
                  </div>
                </div>
                <div className="contribution-bar-container">
                  <div 
                    className="contribution-bar"
                    style={{ width: `${contrib.percentage || 0}%` }}
                  />
                </div>
                <div className="contribution-percent">
                  {(contrib.percentage || 0).toFixed(1)}%
                </div>
              </div>
            ))
          )}
        </div>
      </Modal>
    </div>
  );
}

export default DashboardPage;
