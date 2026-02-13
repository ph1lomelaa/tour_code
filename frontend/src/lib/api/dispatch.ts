/**
 * Dispatch API client - очередь отправки тур-кодов.
 */
import { api } from './axios';

export interface DispatchPerson {
  surname: string;
  name: string;
  document: string;
  package_name?: string;
  tour_name?: string;
}

export interface DispatchEnqueueRequest {
  tour: {
    spreadsheet_id: string;
    spreadsheet_name: string;
    sheet_name: string;
    date_start: string;
    date_end: string;
    days: number;
    route: string;
    departure_city: string;
  };
  selection: {
    country: string;
    hotel: string;
    flight: string;
    remark?: string;
  };
  results: {
    matched: DispatchPerson[];
    in_sheet_not_in_manifest: DispatchPerson[];
    in_manifest_not_in_sheet: DispatchPerson[];
  };
  manifest_filename?: string;
  max_attempts?: number;
}

export interface DispatchJobResponse {
  id: string;
  status: string;
  attempt_count: number;
  max_attempts: number;
  celery_task_id?: string | null;
  error_message?: string | null;
  created_at: string;
  updated_at: string;
  next_attempt_at?: string | null;
  sent_at?: string | null;
}

export const enqueueDispatchJob = async (
  payload: DispatchEnqueueRequest
): Promise<DispatchJobResponse> => {
  const response = await api.post<DispatchJobResponse>('/api/v1/dispatch/jobs/enqueue', payload);
  return response.data;
};

export const getDispatchJob = async (jobId: string): Promise<DispatchJobResponse> => {
  const response = await api.get<DispatchJobResponse>(`/api/v1/dispatch/jobs/${jobId}`);
  return response.data;
};

export const retryDispatchJob = async (jobId: string): Promise<DispatchJobResponse> => {
  const response = await api.post<DispatchJobResponse>(`/api/v1/dispatch/jobs/${jobId}/retry`);
  return response.data;
};
