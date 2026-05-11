import axios from 'axios';
import { getToken } from '../utils/auth';

const API_BASE_URL = 'http://localhost:8000/api/v1';

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
  login: (username, password) =>
    apiClient.post('/auth/login', { username, password }),

  register: (userData) =>
    apiClient.post('/auth/register', userData),

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
    if (file) {
      formData.append('file', file);
    }
    return apiClient.post('/student/activities', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
  },

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