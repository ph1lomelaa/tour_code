/**
 * Manifest API - загрузка и сравнение манифестов
 */
import { api } from './axios';

export interface Pilgrim {
  surname: string;
  name: string;
  document: string;
  manager?: string;
}

export interface UploadManifestResponse {
  success: boolean;
  pilgrims: Pilgrim[];
  count: number;
  message: string;
}

export interface CompareRequest {
  spreadsheet_id: string;
  sheet_name: string;
  manifest_pilgrims: Pilgrim[];
}

export interface CompareResponse {
  success: boolean;
  matched: Pilgrim[];
  in_sheet_not_in_manifest: Pilgrim[];
  in_manifest_not_in_sheet: Pilgrim[];
  message: string;
}

/**
 * Загружает и парсит Excel манифест
 */
export const uploadManifest = async (file: File): Promise<UploadManifestResponse> => {
  const formData = new FormData();
  formData.append('file', file);

  const response = await api.post<UploadManifestResponse>(
    '/api/v1/manifest/upload',
    formData,
    {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    }
  );

  return response.data;
};

/**
 * Сравнивает манифест с Google Sheets
 */
export const compareManifestWithSheet = async (
  request: CompareRequest
): Promise<CompareResponse> => {
  const response = await api.post<CompareResponse>(
    '/api/v1/manifest/compare',
    request
  );

  return response.data;
};
