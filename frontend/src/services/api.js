import axios from 'axios';

//const API_BASE_URL = 'http://127.0.0.1:8000';
import { API_BASE_URL } from './config';
const api = axios.create({
  baseURL: API_BASE_URL,
});

// Add response interceptor to handle errors properly
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 429) {
      // Rate limit exceeded
      throw new Error('Too many requests. Please wait a minute and try again.');
    }
    
    // 👇 ADD THIS - Extract error message from FastAPI response
    if (error.response?.data?.detail) {
      // FastAPI validation errors come in 'detail'
      if (typeof error.response.data.detail === 'string') {
        throw new Error(error.response.data.detail);
      } else if (Array.isArray(error.response.data.detail)) {
        // FastAPI validation errors array
        const messages = error.response.data.detail.map(err => err.msg).join(', ');
        throw new Error(messages);
      }
    }
    
    if (error.response?.data?.message) {
      throw new Error(error.response.data.message);
    }
    // 👆 END FIX
    
    throw error;
  }
);

// Get ATS Score
export const getATSScore = async (resumeFile, jobUrl) => {
  const formData = new FormData();
  formData.append('resume', resumeFile);
  formData.append('job_url', jobUrl);
  
  const response = await api.post('/auto_match', formData, {
    headers: { 'Content-Type': 'multipart/form-data' }
  });
  
  return response.data;
};

// Auto-fill Application
export const applyToJob = async (resumeFile, jobUrl) => {
  const formData = new FormData();
  formData.append('resume', resumeFile);
  formData.append('job_url', jobUrl);
  
  const response = await api.post('/api/apply', formData, {
    headers: { 'Content-Type': 'multipart/form-data' }
  });
  
  return response.data;
};

export default api;