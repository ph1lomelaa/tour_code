import { api } from './axios';

export interface PilgrimListItem {
  id: string;
  surname: string;
  name: string;
  document: string;
  package_name: string;
  tour_code: string;
  tour_code_old?: string;
  tour_id: string;
  tour_name: string;
  tour_route: string;
  date_start: string;
  date_end: string;
  /** Когда получен тур-код (ISO, UTC); пусто у старых записей. */
  tour_code_created_at?: string;
  /** Кто его создал. */
  tour_code_created_by?: string;
}

export interface PilgrimListResponse {
  items: PilgrimListItem[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export interface PilgrimSearchParams {
  surname?: string;
  name?: string;
  document?: string;
  page?: number;
  page_size?: number;
}

export const getPilgrims = async (params: PilgrimSearchParams): Promise<PilgrimListResponse> => {
  const response = await api.get<PilgrimListResponse>('/api/v1/pilgrims', { params });
  return response.data;
};
