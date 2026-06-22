import axios from 'axios';
import { getToken } from '../utils/auth';

// API base URL. Overridable at build time via REACT_APP_API_BASE_URL so the
// same source runs on a dev laptop and on the school server without edits.
// CRA inlines REACT_APP_* at BUILD time (npm run build), not at runtime, so
// the server value must be set before building. With no env var set, this
// falls back to the local dev default, preserving the existing workflow.
// Server options (set whichever matches how the front end is served):
//   - same origin behind a reverse proxy:  REACT_APP_API_BASE_URL=/api/v1
//   - separate host/port:                  REACT_APP_API_BASE_URL=http://<server-address>:8000/api/v1
const API_BASE_URL =
  process.env.REACT_APP_API_BASE_URL || 'http://localhost:8000/api/v1';

const apiClient = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Add token to requests
apiClient.interceptors.request.use((config) => {
  const token = getToken();
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Re-export the base URL for callers that need to compose absolute URLs
// (e.g. getFileUrl below). Keeps the literal in one place.
export { API_BASE_URL };

// API methods
export const auth = {
  // NOTE: public self-registration has been removed. Accounts are created by
  // an administrator via the admin endpoints below (admin.createUser), which
  // are guarded server-side by get_current_admin. There is intentionally no
  // auth.register method any more.
  login: (username, password) =>
    apiClient.post('/auth/login', { username, password }),

  me: () =>
    apiClient.get('/auth/me'),
};

export const student = {
  getDashboard: () =>
    apiClient.get('/student/dashboard'),

  getObjectives: (quadrantId = null) =>
    apiClient.get('/student/objectives', { params: { quadrant_id: quadrantId } }),

  uploadEvidence: (formData) =>
    apiClient.post('/student/upload', formData, {
      headers: { 'Content-Type': 'multipart/form-data' }
    }),

  getSubmissions: (status = 'all') =>
    apiClient.get('/student/submissions', { params: { status } }),

  // GET /student/journey — Chunk 25
  // Returns the authenticated student's Year 7→12 timeline with
  // milestones for the curated hero students; empty per-year buckets
  // otherwise. See StudentJourney in backend/schemas.py for the
  // exact response shape.
  getJourney: () =>
    apiClient.get('/student/journey'),

  // GET /student/diploma-award — Chunk 31
  // Read-only graduation view for the signed-in student. Returns
  // { student_id, eligible_for_diploma, award } where award is null
  // until a teacher records one, otherwise { award_level, selected_at }.
  // Eligibility = every active mandatory objective approved; the award
  // band (Pass/Merit/Distinction) is teacher-selected, never computed.
  getDiplomaAward: () =>
    apiClient.get('/student/diploma-award'),

  // GET /student/skills-profile — Chunk 33
  // The signed-in student's 16-dimension Misk Skills Profile, computed live.
  // Returns { dimensions: [{dimension, group, score, ...}], acp_average,
  // vaa_average, overall_average }. group is 'ACP' or 'VAA' (the two radars).
  getSkillsProfile: () =>
    apiClient.get('/student/skills-profile'),

  // ----- Misk Core -----

  // GET /student/activity-categories
  getActivityCategories: () =>
    apiClient.get('/student/activity-categories'),

  // POST /student/activities (multipart)
  // Accepts a plain object so callers don't need to remember the
  // multipart contract (snake_case field names, JSON-stringified tags).
  // {
  //   categoryId:    number,         required
  //   title:         string,         required
  //   description:   string | null,  optional
  //   activityDate:  string,         required, ISO 'YYYY-MM-DD'
  //   tags:          string[],       optional, defaults to []
  //   file:          File | null,    optional
  // }
  logActivity: ({
    categoryId,
    title,
    description = null,
    activityDate,
    tags = [],
    skills = [],
    file = null,
  }) => {
    const formData = new FormData();
    formData.append('category_id', String(categoryId));
    formData.append('title', title);
    if (description !== null && description !== undefined) {
      formData.append('description', description);
    }
    formData.append('activity_date', activityDate);
    formData.append('tags', JSON.stringify(Array.isArray(tags) ? tags : []));
    // Up to 3 { dimension, justification } skill claims; backend validates.
    formData.append('skills', JSON.stringify(Array.isArray(skills) ? skills : []));
    if (file) {
      formData.append('file', file);
    }
    return apiClient.post('/student/activities', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
  },

  // GET /student/skill-dimensions — grouped 31 dimensions for the skill picker.
  // Returns { acp: [{group, leaves[]}], vaa: [{cluster, dimensions[]}] }.
  getSkillDimensions: () => apiClient.get('/student/skill-dimensions'),

  // GET /student/activities
  // { categoryId?: number, limit?: number }
  getActivities: ({ categoryId, limit } = {}) => {
    const params = {};
    if (categoryId !== undefined && categoryId !== null) {
      params.category_id = categoryId;
    }
    if (limit !== undefined && limit !== null) {
      params.limit = limit;
    }
    return apiClient.get('/student/activities', { params });
  },

  // ----- File access -----

  // Fetch the bytes for an uploaded file via the authenticated
  // /files/{stored_filename} route, returning a small descriptor
  // { blob, mimeType, originalFilename } that components can convert
  // to an object URL for <img>, <iframe>, or download triggers.
  //
  // We need this helper because <img src=...> / <a href=...> cannot
  // attach the Bearer token; we have to fetch via axios (which the
  // interceptor authenticates) and then hand the bytes to the DOM.
  fetchFileBlob: async (storedFilename, { download = false } = {}) => {
    const response = await apiClient.get(`/files/${encodeURIComponent(storedFilename)}`, {
      params: download ? { download: 1 } : undefined,
      responseType: 'blob',
    });
    const disposition = response.headers['content-disposition'] || '';
    // Extract filename="..." from Content-Disposition; fall back to the
    // stored filename if the server didn't echo one.
    const match = disposition.match(/filename="?([^"]+)"?/i);
    const originalFilename = match ? match[1] : storedFilename;
    return {
      blob: response.data,
      mimeType: response.headers['content-type'] || 'application/octet-stream',
      originalFilename,
    };
  },
};

export const teacher = {
  getSubmissions: (status = 'all') =>
    apiClient.get('/teacher/submissions', { params: { status } }),

  getSubmissionDetail: (submissionId) =>
    apiClient.get(`/teacher/submission/${submissionId}`),

  submitReview: (reviewData) =>
    apiClient.post('/teacher/review', reviewData),

  getStudentReport: (studentId) =>
    apiClient.get(`/teacher/report/${studentId}`),

  // GET /teacher/student-profile/{studentId}
  // { categoryId?: number, limit?: number } query params optional.
  getStudentProfile: (studentId, { categoryId, limit } = {}) => {
    const params = {};
    if (categoryId !== undefined && categoryId !== null) {
      params.category_id = categoryId;
    }
    if (limit !== undefined && limit !== null) {
      params.limit = limit;
    }
    return apiClient.get(`/teacher/student-profile/${studentId}`, { params });
  },

  // POST /teacher/objective-result — Chunk 31
  // Record an exam outcome for a result-based academic objective
  // (IELTS / IGCSE / IAL / Qudurat / Tahsili). Score-based titles send
  // `score`; grade-based titles (IGCSE/IAL) send `grades` (string[]).
  // `attempts` applies to Qudurat (≤5) / Tahsili (≤2); defaults to 1.
  // The backend validates title↔payload and stores result_value +
  // attempts on the student's progress row; it does NOT change the
  // objective's approval status.
  recordObjectiveResult: ({ studentId, objectiveId, score, grades, attempts }) =>
    apiClient.post('/teacher/objective-result', {
      student_id: studentId,
      objective_id: objectiveId,
      score: score ?? null,
      grades: grades ?? null,
      attempts: attempts ?? 1,
    }),

  // GET /teacher/diploma-award/{studentId} — Chunk 31
  // Returns { student_id, student_name, eligible_for_diploma, award }
  // where award is null until recorded, else
  // { award_level, selected_by, selected_by_name, selected_at, notes }.
  getDiplomaAward: (studentId) =>
    apiClient.get(`/teacher/diploma-award/${studentId}`),

  // POST /teacher/diploma-award — Chunk 31
  // Manually record the formal diploma band for an eligible student.
  // 409 DIPLOMA_NOT_ELIGIBLE if not every active mandatory objective is
  // approved. award_level must be one of Pass / Merit / Distinction.
  setDiplomaAward: ({ studentId, awardLevel, notes }) =>
    apiClient.post('/teacher/diploma-award', {
      student_id: studentId,
      award_level: awardLevel,
      notes: notes ?? null,
    }),

  // GET /teacher/activities — Chunk 32
  // Misk Core activity review queue. `status` is one of
  // pending_review | approved | rejected | all (default pending_review).
  // Returns { activities: [...] } with each item carrying student_name,
  // category_name, the file descriptor, tags, status and review fields.
  getActivitiesForReview: (status = 'pending_review') =>
    apiClient.get('/teacher/activities', { params: { status } }),

  // POST /teacher/activity-review — Chunk 32 (+ per-claim skill levels)
  // Approve or reject a Misk Core activity. decision is 'approved' or
  // 'rejected'; feedback is optional and surfaced back to the student.
  // skillLevels is an array of { rating_id, level } (0=Not evident .. 3=Embedded)
  // applied to the activity's skill claims on approval.
  reviewActivity: ({ activityId, decision, feedback, skillLevels = [] }) =>
    apiClient.post('/teacher/activity-review', {
      activity_id: activityId,
      decision,
      feedback: feedback ?? null,
      skill_levels: Array.isArray(skillLevels) ? skillLevels : [],
    }),

  // GET /teacher/skills-profile/{studentId} — Chunk 33
  // A student's 16-dimension Misk Skills Profile (teacher view), computed live.
  getSkillsProfile: (studentId) =>
    apiClient.get(`/teacher/skills-profile/${studentId}`),

  // GET /teacher/students — full student roster for pickers (every student,
  // not only those with submissions). Returns { students: [{ id, full_name }] }.
  getStudents: () =>
    apiClient.get('/teacher/students'),

  // GET /teacher/report-pdf/{studentId}
  // Streams a generated PDF report (formal diploma + skills profile). Returns a
  // { blob, filename } descriptor the caller turns into a download. We fetch via
  // axios (responseType 'blob') because a plain <a href> can't attach the Bearer
  // token — same constraint as student.fetchFileBlob. filename comes from the
  // server's Content-Disposition, with a sensible fallback.
  downloadStudentReport: async (studentId) => {
    const response = await apiClient.get(`/teacher/report-pdf/${studentId}`, {
      responseType: 'blob',
    });
    const disposition = response.headers['content-disposition'] || '';
    const match = disposition.match(/filename="?([^"]+)"?/i);
    const filename = match ? match[1] : `Misk_Diploma_Report_${studentId}.pdf`;
    return { blob: response.data, filename };
  },
};

export const admin = {
  // GET /admin/users — list student + teacher accounts (admin only).
  // Returns { users: [{ id, username, full_name, role, current_grade, entry_grade }] }.
  listUsers: () =>
    apiClient.get('/admin/users'),

  // POST /admin/create-user — create a student or teacher (admin only).
  // The server generates the login username from usernameBase + a 4-digit
  // suffix and returns the created account (including the generated username).
  // For teachers, currentGrade/entryGrade are ignored by the server.
  // {
  //   role:         'student' | 'teacher',  required
  //   fullName:     string,                 required
  //   usernameBase: string,                 required (first name, a-z)
  //   password:     string,                 required (min 8)
  //   currentGrade: number | null,          required for students (4-12)
  //   entryGrade:   number | null,          required for students (4-12)
  // }
  createUser: ({
    role,
    fullName,
    usernameBase,
    password,
    currentGrade = null,
    entryGrade = null,
  }) =>
    apiClient.post('/admin/create-user', {
      role,
      full_name: fullName,
      username_base: usernameBase,
      password,
      current_grade: currentGrade,
      entry_grade: entryGrade,
    }),

  // POST /admin/reset-password — set a new password for a student or teacher
  // (admin only). Admin accounts cannot be reset here.
  // { userId: number, newPassword: string (min 8) }
  resetPassword: ({ userId, newPassword }) =>
    apiClient.post('/admin/reset-password', {
      user_id: userId,
      new_password: newPassword,
    }),
};

// Build an absolute URL to an authenticated file. NOTE: this URL is NOT
// directly usable in <img src> or <a href> — those requests do not carry
// the Bearer token, so the server will respond 401. Use student.fetchFileBlob
// for actual rendering/download in the UI; getFileUrl is for cases where
// a plain URL string is needed (logs, OpenAPI debugging, future cookie auth).
export const getFileUrl = (storedFilename, inline = true) => {
  const safe = encodeURIComponent(storedFilename);
  const query = inline ? '' : '?download=1';
  return `${API_BASE_URL}/files/${safe}${query}`;
};

export default apiClient;