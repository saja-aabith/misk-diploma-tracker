import React, { useState, useEffect } from 'react';
import { student } from '../api/client';

/**
 * AttachmentLink — lazy-fetches an authenticated file via fetchFileBlob,
 * converts to an object URL, and triggers a download on click. Used for
 * Misk Core activity attachments and evidence submission files in both
 * the student and teacher dashboards.
 *
 * Pattern:
 *   - Idle:    show a small "Open <filename>" button.
 *   - Loading: show "Opening…" while the blob fetches.
 *   - Error:   show "Could not open" with the underlying message in title.
 *
 * The blob's object URL is revoked on unmount so we don't leak.
 *
 * NOTE: this uses `student.fetchFileBlob` for both student and teacher
 * callers — that's intentional. The backend's /api/v1/files/{stored_filename}
 * route enforces ownership server-side (Chunk 5): teachers can read any
 * file, students can read their own. The client method is named after
 * its module of residence (api/client.js student object), not the role
 * of the caller.
 */
function AttachmentLink({ storedFilename, originalFilename }) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [objectUrl, setObjectUrl] = useState(null);

  useEffect(() => {
    return () => {
      if (objectUrl) {
        URL.revokeObjectURL(objectUrl);
      }
    };
  }, [objectUrl]);

  const handleOpen = async () => {
    setLoading(true);
    setError('');
    try {
      const { blob, originalFilename: serverName } = await student.fetchFileBlob(storedFilename);
      const url = URL.createObjectURL(blob);
      setObjectUrl(url);
      const a = document.createElement('a');
      a.href = url;
      a.target = '_blank';
      a.rel = 'noopener';
      a.download = originalFilename || serverName || storedFilename;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
    } catch (err) {
      const detail = err?.response?.data?.detail;
      const message =
        (detail && typeof detail === 'object' && detail.message) ||
        (typeof detail === 'string' && detail) ||
        'Could not open file';
      setError(message);
    } finally {
      setLoading(false);
    }
  };

  if (!storedFilename) return null;

  const label = originalFilename || 'attachment';

  return (
    <button
      type="button"
      onClick={handleOpen}
      disabled={loading}
      title={error || ''}
      style={{
        background: 'transparent',
        border: 'none',
        padding: 0,
        color: '#02664b',
        fontWeight: 700,
        textDecoration: 'underline',
        cursor: loading ? 'progress' : 'pointer',
      }}
    >
      {loading ? 'Opening…' : error ? 'Could not open' : `Open ${label}`}
    </button>
  );
}

export default AttachmentLink;