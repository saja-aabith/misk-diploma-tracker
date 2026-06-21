import React, { useState, useEffect } from 'react';
import { student } from '../api/client';

// Mirrors UploadModal.js structure — same overlay/content/header
// pattern, same error-message rendering, same .btn-login submit, same
// "Loading…/Submitting…" disabled-button affordance. Differences are
// limited to the inputs Misk Core needs: category picker, activity
// date, tags, optional file.
//
// Props:
//   onClose()                 — close the modal (parent owns visibility)
//   onSuccess(activityData?)  — invoked after a successful log;
//                               activityData is the created ActivityOut
//                               so the parent can prepend it to a feed.
//                               Parent may ignore the arg.

const TAG_MAX_LEN = 32;
const MAX_TAGS = 10;
const TITLE_MAX_LEN = 200;
const DESCRIPTION_MAX_LEN = 4000;
const MAX_SKILLS = 3;
const JUSTIFICATION_MAX_LEN = 2000;

// Today in ISO YYYY-MM-DD, used as the date input's default and `max`
// attribute. Backend rejects future dates anyway (Chunk 6 schema), but
// capping in the picker prevents an avoidable round-trip.
function todayIso() {
  const d = new Date();
  const yyyy = d.getFullYear();
  const mm = String(d.getMonth() + 1).padStart(2, '0');
  const dd = String(d.getDate()).padStart(2, '0');
  return `${yyyy}-${mm}-${dd}`;
}

// Split a comma-separated string into a clean tag list:
//   - trim
//   - lowercase (matches the backend ActivityLogIn validator)
//   - drop empties
//   - dedupe
//   - per-tag length cap
//   - count cap
// Returns { tags, error }. error is a user-facing string when invalid.
function parseTags(raw) {
  if (!raw || !raw.trim()) {
    return { tags: [], error: null };
  }
  const seen = new Set();
  const tags = [];
  for (const part of raw.split(',')) {
    const tag = part.trim().toLowerCase();
    if (!tag) continue;
    if (tag.length > TAG_MAX_LEN) {
      return {
        tags: [],
        error: `Tag too long (max ${TAG_MAX_LEN} characters): "${tag}"`,
      };
    }
    if (seen.has(tag)) continue;
    seen.add(tag);
    tags.push(tag);
  }
  if (tags.length > MAX_TAGS) {
    return { tags: [], error: `Too many tags (max ${MAX_TAGS}).` };
  }
  return { tags, error: null };
}

// Tolerant error-detail extractor: backend returns a string for legacy
// handlers and a {code, message} dict for migrated handlers (Chunk 6).
// We accept either and fall back to a generic message.
function extractErrorMessage(err, fallback) {
  const detail = err?.response?.data?.detail;
  if (typeof detail === 'string') return detail;
  if (detail && typeof detail === 'object') {
    if (typeof detail.message === 'string') return detail.message;
  }
  return fallback;
}

function ActivityLogModal({ onClose, onSuccess }) {
  const [categories, setCategories] = useState([]);
  const [loadingCategories, setLoadingCategories] = useState(true);

  const [categoryId, setCategoryId] = useState('');
  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [activityDate, setActivityDate] = useState(todayIso());
  const [tagsInput, setTagsInput] = useState('');
  const [file, setFile] = useState(null);

  // Misk Core skill claims: up to MAX_SKILLS of the 31 dimensions, each with a
  // justification. Loaded grouped from the backend so the locked dimension
  // strings are never hardcoded here.
  const [skillGroups, setSkillGroups] = useState({ acp: [], vaa: [] });
  const [selectedSkills, setSelectedSkills] = useState([]); // [{ dimension, justification }]

  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    let cancelled = false;
    student
      .getSkillDimensions()
      .then((res) => {
        if (cancelled) return;
        setSkillGroups({ acp: res?.data?.acp || [], vaa: res?.data?.vaa || [] });
      })
      .catch(() => {
        // Non-fatal: skill tagging is optional; the rest of the form still works.
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const isSkillSelected = (dim) => selectedSkills.some((s) => s.dimension === dim);
  const toggleSkill = (dim) => {
    setError('');
    setSelectedSkills((prev) => {
      if (prev.some((s) => s.dimension === dim)) {
        return prev.filter((s) => s.dimension !== dim);
      }
      if (prev.length >= MAX_SKILLS) return prev; // cap at MAX_SKILLS
      return [...prev, { dimension: dim, justification: '' }];
    });
  };
  const setJustification = (dim, text) =>
    setSelectedSkills((prev) =>
      prev.map((s) => (s.dimension === dim ? { ...s, justification: text } : s)));

  useEffect(() => {
    let cancelled = false;
    student
      .getActivityCategories()
      .then((res) => {
        if (cancelled) return;
        const list = res?.data?.categories || [];
        setCategories(list);
      })
      .catch((err) => {
        if (cancelled) return;
        setError(extractErrorMessage(err, 'Could not load activity categories.'));
      })
      .finally(() => {
        if (cancelled) return;
        setLoadingCategories(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const handleSubmit = async (e) => {
    e.preventDefault();

    // Basic field validation. The backend validates again (source of
    // truth), but pre-flighting client-side gives faster, kinder errors.
    if (!categoryId) {
      setError('Please choose a category.');
      return;
    }
    const trimmedTitle = title.trim();
    if (!trimmedTitle) {
      setError('Please enter a title.');
      return;
    }
    if (trimmedTitle.length > TITLE_MAX_LEN) {
      setError(`Title must be ${TITLE_MAX_LEN} characters or fewer.`);
      return;
    }
    const trimmedDescription = description.trim();
    if (trimmedDescription.length > DESCRIPTION_MAX_LEN) {
      setError(`Description must be ${DESCRIPTION_MAX_LEN} characters or fewer.`);
      return;
    }
    if (!activityDate) {
      setError('Please pick the activity date.');
      return;
    }
    if (activityDate > todayIso()) {
      setError('Activity date cannot be in the future.');
      return;
    }
    const { tags, error: tagsError } = parseTags(tagsInput);
    if (tagsError) {
      setError(tagsError);
      return;
    }

    // Each selected skill needs a justification (backend enforces this too).
    for (const s of selectedSkills) {
      if (!s.justification.trim()) {
        setError(`Add a justification for "${s.dimension}".`);
        return;
      }
    }

    setSubmitting(true);
    setError('');

    try {
      const res = await student.logActivity({
        categoryId: Number(categoryId),
        title: trimmedTitle,
        description: trimmedDescription || null,
        activityDate,
        tags,
        skills: selectedSkills.map((s) => ({
          dimension: s.dimension,
          justification: s.justification.trim(),
        })),
        file: file || null,
      });
      onSuccess(res?.data);
    } catch (err) {
      setError(extractErrorMessage(err, 'Could not log activity.'));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h3>Log Misk Core Activity</h3>
          <button className="btn-close" onClick={onClose}>×</button>
        </div>

        {error && <div className="error-message">{error}</div>}

        <form onSubmit={handleSubmit}>
          <div className="form-group">
            <label>Category</label>
            <select
              value={categoryId}
              onChange={(e) => setCategoryId(e.target.value)}
              disabled={loadingCategories || submitting}
              required
            >
              <option value="" disabled>
                {loadingCategories ? 'Loading categories…' : 'Choose a category'}
              </option>
              {categories.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name}
                </option>
              ))}
            </select>
          </div>

          <div className="form-group">
            <label>Title</label>
            <input
              type="text"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="e.g. Volunteered at hospital"
              maxLength={TITLE_MAX_LEN}
              disabled={submitting}
              required
            />
          </div>

          <div className="form-group">
            <label>Description (Optional)</label>
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="What did you do? What did you learn?"
              maxLength={DESCRIPTION_MAX_LEN}
              disabled={submitting}
            />
          </div>

          <div className="form-group">
            <label>Activity Date</label>
            <input
              type="date"
              value={activityDate}
              max={todayIso()}
              onChange={(e) => setActivityDate(e.target.value)}
              disabled={submitting}
              required
            />
          </div>

          <div className="form-group">
            <label>Tags (Optional)</label>
            <input
              type="text"
              value={tagsInput}
              onChange={(e) => setTagsInput(e.target.value)}
              placeholder="e.g. leadership, community, arabic"
              disabled={submitting}
            />
            <small style={{ color: '#7f8c8d' }}>
              Comma-separated. Up to {MAX_TAGS} tags, each up to {TAG_MAX_LEN} characters.
            </small>
          </div>

          <div className="form-group">
            <label>Skills this evidences (max {MAX_SKILLS}) — Optional</label>
            <small style={{ color: '#7f8c8d', display: 'block', marginBottom: 6 }}>
              Tag up to {MAX_SKILLS} skills this activity demonstrates and say why.
              A teacher reviews each. {selectedSkills.length}/{MAX_SKILLS} selected.
            </small>
            <div
              style={{
                maxHeight: 200,
                overflowY: 'auto',
                border: '1px solid #e1e8e5',
                borderRadius: 6,
                padding: 8,
              }}
            >
              {[
                ...skillGroups.acp.map((g) => ({ label: g.group, dims: g.leaves })),
                ...skillGroups.vaa.map((c) => ({ label: c.cluster, dims: c.dimensions })),
              ].map((grp) => (
                <div key={grp.label} style={{ marginBottom: 6 }}>
                  <div style={{ fontSize: 11, fontWeight: 700, color: '#02664b' }}>
                    {grp.label}
                  </div>
                  {grp.dims.map((dim) => {
                    const checked = isSkillSelected(dim);
                    const capped = !checked && selectedSkills.length >= MAX_SKILLS;
                    return (
                      <label
                        key={dim}
                        style={{
                          display: 'flex',
                          alignItems: 'center',
                          gap: 6,
                          fontSize: 13,
                          color: capped ? '#aab2ae' : '#334',
                          padding: '1px 0',
                        }}
                      >
                        <input
                          type="checkbox"
                          checked={checked}
                          disabled={submitting || capped}
                          onChange={() => toggleSkill(dim)}
                        />
                        {dim}
                      </label>
                    );
                  })}
                </div>
              ))}
            </div>
            {selectedSkills.map((s) => (
              <div key={s.dimension} style={{ marginTop: 8 }}>
                <label style={{ fontSize: 12, fontWeight: 700 }}>
                  Why does this show “{s.dimension}”?
                </label>
                <textarea
                  value={s.justification}
                  onChange={(e) => setJustification(s.dimension, e.target.value)}
                  placeholder="Explain how this activity demonstrates this skill…"
                  maxLength={JUSTIFICATION_MAX_LEN}
                  disabled={submitting}
                  style={{ width: '100%', minHeight: 48 }}
                />
              </div>
            ))}
          </div>

          <div className="form-group">
            <label>Attachment (Optional)</label>
            <input
              type="file"
              accept=".pdf,.jpg,.jpeg,.png,.docx,.mp4"
              onChange={(e) => setFile(e.target.files?.[0] || null)}
              disabled={submitting}
            />
            <small style={{ color: '#7f8c8d' }}>
              Allowed: PDF, JPG, PNG, DOCX, MP4 (max 50MB)
            </small>
          </div>

          <button
            type="submit"
            className="btn-login"
            disabled={submitting || loadingCategories}
          >
            {submitting ? 'Logging…' : 'Log Activity'}
          </button>
        </form>
      </div>
    </div>
  );
}

export default ActivityLogModal;