import { api } from './axios';

export interface DashboardStatsResponse {
  total_tours: number;
  total_pilgrims: number;
  sent_jobs: number;
  queued_jobs: number;
  failed_jobs: number;
}

export interface RecentTourItem {
  id: string;
  sheet_name: string;
  route: string;
  date_start: string;
  date_end: string;
  pilgrims_count: number;
  dispatch_status: string | null;
  created_at: string;
}

export interface RecentJobItem {
  id: string;
  tour_sheet_name: string;
  status: string;
  attempt_count: number;
  max_attempts: number;
  error_message: string | null;
  created_at: string;
  sent_at: string | null;
}

export interface DashboardRecentResponse {
  recent_tours: RecentTourItem[];
  recent_jobs: RecentJobItem[];
}

export const getDashboardStats = async (): Promise<DashboardStatsResponse> => {
  const response = await api.get<DashboardStatsResponse>('/api/v1/dashboard/stats');
  return response.data;
};

export const getDashboardRecent = async (): Promise<DashboardRecentResponse> => {
  const response = await api.get<DashboardRecentResponse>('/api/v1/dashboard/recent');
  return response.data;
};
