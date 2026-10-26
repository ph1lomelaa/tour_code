/**
 * Settings API client - раздел «Настройки» (справочники).
 */
import axios from 'axios';
import { api } from './axios';

export type ReferenceEntity = 'airlines' | 'countries' | 'hotels' | 'routes' | 'touragents';

export interface ReferenceItem {
  id: string;
  code?: string;
  name?: string;
  name_ru?: string;
  name_en?: string;
  city?: string;
  departure_city?: string;
  bin?: string;
  is_default?: boolean;
  sort_order: number;
  is_active: boolean;
  kamkor_verified_at?: string | null;
}

export type ReferenceData = Record<ReferenceEntity, ReferenceItem[]>;

export interface Verification {
  status: 'found' | 'not_found' | 'unchecked' | 'invalid';
  message: string;
  suggestions: string[];
  extra: Record<string, string>;
}

export interface KamkorAccount {
  key: string;
  label: string;
  login: string;
  ok: boolean;
  error: string;
}

export interface FailedDispatchJob {
  id: string;
  tour_label: string;
  touragent: string;
  pilgrims: number;
  error_message: string;
  attempt_count: number;
  updated_at: string | null;
}

export interface AuditItem {
  id: string;
  entity: ReferenceEntity;
  entity_id: string;
  action: 'create' | 'update' | 'delete' | 'restore';
  before: Partial<ReferenceItem> | null;
  after: Partial<ReferenceItem> | null;
  created_at: string;
}

export const errorDetail = (error: unknown, fallback = 'Ошибка запроса'): string => {
  if (axios.isAxiosError(error)) {
    const detail = error.response?.data?.detail;
    if (typeof detail === 'string') return detail;
    if (error.message) return error.message;
  }
  return fallback;
};

export const getReferenceData = async (): Promise<ReferenceData> => {
  const response = await api.get<ReferenceData>('/api/v1/settings/reference');
  return response.data;
};

export const listEntity = async (entity: ReferenceEntity): Promise<ReferenceItem[]> => {
  const response = await api.get<{ items: ReferenceItem[] }>(`/api/v1/settings/${entity}`);
  return response.data.items;
};

export const verifyEntity = async (
  entity: ReferenceEntity,
  data: Partial<ReferenceItem>
): Promise<Verification> => {
  const response = await api.post<Verification>(`/api/v1/settings/${entity}/verify`, { data });
  return response.data;
};

export const createEntity = async (
  entity: ReferenceEntity,
  data: Partial<ReferenceItem>,
  force = false
): Promise<ReferenceItem> => {
  const response = await api.post<{ item: ReferenceItem }>(`/api/v1/settings/${entity}`, { data, force });
  return response.data.item;
};

export const updateEntity = async (
  entity: ReferenceEntity,
  id: string,
  data: Partial<ReferenceItem>,
  force = false
): Promise<ReferenceItem> => {
  const response = await api.patch<{ item: ReferenceItem }>(`/api/v1/settings/${entity}/${id}`, { data, force });
  return response.data.item;
};

export const deleteEntity = async (entity: ReferenceEntity, id: string): Promise<void> => {
  await api.delete(`/api/v1/settings/${entity}/${id}`);
};

export const restoreEntity = async (entity: ReferenceEntity, id: string): Promise<void> => {
  await api.post(`/api/v1/settings/${entity}/${id}/restore`);
};

export const checkKamkorAccounts = async (): Promise<KamkorAccount[]> => {
  const response = await api.get<{ accounts: KamkorAccount[] }>('/api/v1/settings/kamkor/accounts');
  return response.data.accounts;
};

export const getFailedDispatchJobs = async (): Promise<FailedDispatchJob[]> => {
  const response = await api.get<{ jobs: FailedDispatchJob[] }>('/api/v1/settings/dispatch/failed');
  return response.data.jobs;
};

export const getAuditLog = async (): Promise<AuditItem[]> => {
  const response = await api.get<{ items: AuditItem[] }>('/api/v1/settings/audit');
  return response.data.items;
};
