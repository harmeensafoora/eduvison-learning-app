import axios from 'axios';

// Create axios instance with base URL pointing to backend
const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api';

const apiClient = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
  withCredentials: true, // Include cookies in requests
});

// Interceptor to add CSRF token from cookie
apiClient.interceptors.request.use((config) => {
  const csrfToken = getCookie('eduvision_csrf');
  if (csrfToken) {
    config.headers['X-CSRF-Token'] = csrfToken;
  }
  return config;
}, (error) => {
  return Promise.reject(error);
});

/**
 * Utility to get cookie value by name
 */
const getCookie = (name) => {
  const value = `; ${document.cookie}`;
  const parts = value.split(`; ${name}=`);
  if (parts.length === 2) return parts.pop().split(';').shift();
  return null;
};

/**
 * Fetch quiz data from backend
 * @param {string} quizId - Quiz ID
 * @returns {Promise<object>} - Quiz data
 */
export const fetchQuiz = async (quizId) => {
  try {
    const response = await apiClient.get(`/quizzes/${quizId}`);
    return response.data;
  } catch (err) {
    console.error('Failed to fetch quiz:', err);
    throw err;
  }
};

/**
 * Submit quiz responses to backend
 * @param {string} quizId - Quiz ID
 * @param {object} answers - User answers {questionId: answer}
 * @returns {Promise<object>} - Feedback and score
 */
export const submitQuizResponses = async (quizId, answers) => {
  try {
    const response = await apiClient.post(`/quizzes/${quizId}/submit`, {
      answers,
    });
    return response.data;
  } catch (err) {
    console.error('Failed to submit quiz:', err);
    throw err;
  }
};

/**
 * Fetch quiz feedback from backend
 * @param {string} responseId - Quiz response ID
 * @returns {Promise<object>} - Feedback data
 */
export const fetchFeedback = async (responseId) => {
  try {
    const response = await apiClient.get(`/quiz-responses/${responseId}/feedback`);
    return response.data;
  } catch (err) {
    console.error('Failed to fetch feedback:', err);
    throw err;
  }
};

/**
 * Fetch learning concepts for a PDF
 * @param {string} pdfId - PDF ID
 * @returns {Promise<array>} - Array of concepts
 */
export const fetchConcepts = async (pdfId) => {
  try {
    const response = await apiClient.get(`/pdfs/${pdfId}/concepts`);
    return response.data;
  } catch (err) {
    console.error('Failed to fetch concepts:', err);
    throw err;
  }
};

/**
 * Health check endpoint
 * @returns {Promise<object>} - Health status
 */
export const healthCheck = async () => {
  try {
    const response = await apiClient.get('/health');
    return response.data;
  } catch (err) {
    console.error('Health check failed:', err);
    throw err;
  }
};

export default apiClient;
