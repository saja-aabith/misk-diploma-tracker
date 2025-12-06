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
};

export default apiClient;