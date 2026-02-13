import { api } from './axios';

export interface DashboardStatsResponse {
  total_tours: number;
  total_pilgrims: number;
  sent_jobs: number;
}

export const getDashboardStats = async (): Promise<DashboardStatsResponse> => {
  const response = await api.get<DashboardStatsResponse>('/api/v1/dashboard/stats');
  return response.data;
};
