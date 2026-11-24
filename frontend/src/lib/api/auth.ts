/**
 * Auth API — вход, текущий пользователь, приглашения.
 */
import { api } from './axios';

export type UserRole = 'admin' | 'editor' | 'viewer';
export type UserStatus = 'pending' | 'invited' | 'active' | 'disabled';

export interface AppUser {
  id: string;
  email: string;
  full_name: string;
  role: UserRole;
  status: UserStatus;
  last_login_at: string | null;
  created_at: string | null;
  /** Только в списке для админа: действующая ссылка-приглашение. */
  invite_token?: string | null;
}

export interface AuthSession {
  access_token: string;
  token_type: 'bearer';
  user: AppUser;
}

export const TOKEN_KEY = 'token';

export const ROLE_LABELS: Record<UserRole, string> = {
  admin: 'Админ',
  editor: 'Редактор',
  viewer: 'Просмотр',
};

/** email — почта или логин Камкора (для админа). */
export const login = async (email: string, password: string): Promise<AuthSession> => {
  const response = await api.post<AuthSession>('/api/v1/auth/login', { email, password });
  return response.data;
};

export const getMe = async (): Promise<AppUser> => {
  const response = await api.get<AppUser>('/api/v1/auth/me');
  return response.data;
};

export const getInvite = async (token: string): Promise<{ email: string; full_name: string }> => {
  const response = await api.get(`/api/v1/auth/invite/${encodeURIComponent(token)}`);
  return response.data;
};

export const acceptInvite = async (
  token: string,
  full_name: string,
  password: string,
): Promise<AuthSession> => {
  const response = await api.post<AuthSession>(`/api/v1/auth/invite/${encodeURIComponent(token)}`, {
    full_name,
    password,
  });
  return response.data;
};

/** Заявка на доступ: после одобрения админом человек входит по этой почте и паролю. */
export const requestAccess = async (full_name: string, email: string, password: string): Promise<void> => {
  await api.post('/api/v1/auth/request-access', { full_name, email, password });
};
