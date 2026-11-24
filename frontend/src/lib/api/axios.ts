/**
 * Axios client для API запросов
 */
import axios from 'axios';
import { toast } from 'sonner';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

export const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Request interceptor: JWT из localStorage
api.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('token');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

// Response interceptor: 401 — на страницу входа, 403 — нет прав.
const PUBLIC_PATHS = ['/login', '/invite/', '/request-access'];
const isPublicPage = () => PUBLIC_PATHS.some((p) => window.location.pathname.startsWith(p));

api.interceptors.response.use(
  (response) => response,
  (error) => {
    const status = error.response?.status;
    const url: string = error.config?.url || '';
    if (status === 401 && !url.includes('/api/v1/auth/') && !isPublicPage()) {
      localStorage.removeItem('token');
      const next = encodeURIComponent(window.location.pathname + window.location.search);
      window.location.href = `/login?next=${next}`;
    } else if (status === 403 && !url.includes('/api/v1/auth/')) {
      const detail = error.response?.data?.detail;
      toast.error(typeof detail === 'string' ? detail : 'Нет прав на это действие');
    }
    return Promise.reject(error);
  }
);

export default api;
