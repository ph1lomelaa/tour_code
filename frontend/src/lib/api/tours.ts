/**
 * Tours API client
 */
import { api } from './axios';

export interface TourOption {
  spreadsheet_id: string;
  spreadsheet_name: string;
  sheet_name: string;
  date_start: string;  // "17.02.2026"
  date_end: string;    // "24.02.2026"
  days: number;        // 7
  route: string;       // "ALA-JED"
  departure_city: string;  // "Almaty"
}

export interface SearchByDateResponse {
  success: boolean;
  found_count: number;
  tours: TourOption[];
  message: string;
}

export interface PilgrimInPackage {
  surname: string;
  name: string;
  document: string;
  iin?: string;
  manager: string;
  room_type: string;
  meal_type?: string;
}

export interface PackageInfo {
  package_name: string;
  pilgrims: PilgrimInPackage[];
  count: number;
}

export interface SheetPilgrimsResponse {
  success: boolean;
  packages: PackageInfo[];
  total_count: number;
  message: string;
}

/**
 * Поиск туров по дате в Google Sheets
 */
export const searchToursByDate = async (dateShort: string): Promise<SearchByDateResponse> => {
  const response = await api.post<SearchByDateResponse>('/api/v1/tours/search-by-date', {
    date_short: dateShort,
  });
  return response.data;
};

/**
 * Получить паломников из листа, сгруппированных по пакетам
 */
export const getSheetPilgrims = async (
  spreadsheetId: string,
  sheetName: string
): Promise<SheetPilgrimsResponse> => {
  const response = await api.post<SheetPilgrimsResponse>('/api/v1/tours/sheet-pilgrims', {
    spreadsheet_id: spreadsheetId,
    sheet_name: sheetName,
  });
  return response.data;
};

/**
 * Тест подключения к Google Sheets
 */
export const testGoogleSheets = async () => {
  const response = await api.get('/api/v1/tours/test');
  return response.data;
};
