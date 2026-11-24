/**
 * Users API — управление пользователями (только админ).
 */
import { api } from './axios';
import type { AppUser, UserRole } from './auth';

export interface InviteResult {
  user: AppUser;
  invite_token: string;
}

export const inviteLink = (token: string): string => `${window.location.origin}/invite/${token}`;

export const listUsers = async (): Promise<AppUser[]> => {
  const response = await api.get<{ items: AppUser[] }>('/api/v1/users');
  return response.data.items;
};

export const createUser = async (email: string, role: UserRole): Promise<InviteResult> => {
  const response = await api.post<InviteResult>('/api/v1/users', { email, role });
  return response.data;
};

export const updateUser = async (
  id: string,
  patch: { role?: UserRole; is_active?: boolean },
): Promise<AppUser> => {
  const response = await api.patch<AppUser>(`/api/v1/users/${id}`, patch);
  return response.data;
};

export const approveUser = async (id: string, role: UserRole): Promise<AppUser> => {
  const response = await api.post<AppUser>(`/api/v1/users/${id}/approve`, { role });
  return response.data;
};

export const regenerateInvite = async (id: string): Promise<InviteResult> => {
  const response = await api.post<InviteResult>(`/api/v1/users/${id}/invite`);
  return response.data;
};

export const deleteUser = async (id: string): Promise<{ ok: boolean; disabled: boolean }> => {
  const response = await api.delete(`/api/v1/users/${id}`);
  return response.data;
};
