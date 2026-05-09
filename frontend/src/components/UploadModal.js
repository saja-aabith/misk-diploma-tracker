import React, { useState } from 'react';
import { student } from '../api/client';

function UploadModal({ objective, onClose, onSuccess }) {
  const [file, setFile] = useState(null);
  const [description, setDescription] = useState('');
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState('');

  const handleSubmit = async (e) => {
    e.preventDefault();

    if (!file) {
      setError('Please select a file');
      return;
    }

    setUploading(true);
    setError('');

    const formData = new FormData();
    formData.append('file', file);
    formData.append('objective_id', objective.id);
    formData.append('description', description);

    try {
      await student.uploadEvidence(formData);
      onSuccess();
    } catch (err) {
      setError(err.response?.data?.detail || 'Upload failed');
    } finally {
      setUploading(false);
    }
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h3>Upload Evidence</h3>
          <button className="btn-close" onClick={onClose}>×</button>
        </div>

        {error && <div className="error-message">{error}</div>}

        <form onSubmit={handleSubmit}>
          <div className="form-group">
            <label>Objective</label>
            <input type="text" value={objective.title} disabled />
          </div>

          <div className="form-group">
            <label>File</label>
            <input
              type="file"
              accept=".pdf,.jpg,.jpeg,.png,.docx,.mp4"
              onChange={(e) => setFile(e.target.files[0])}
              required
            />
            <small style={{ color: '#7f8c8d' }}>
              Allowed: PDF, JPG, PNG, DOCX, MP4 (max 50MB)
            </small>
          </div>

          <div className="form-group">
            <label>Description (Optional)</label>
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Add any notes about your submission..."
            />
          </div>

          <button type="submit" className="btn-login" disabled={uploading}>
            {uploading ? 'Uploading...' : 'Upload'}
          </button>
        </form>
      </div>
    </div>
  );
}

export default UploadModal;