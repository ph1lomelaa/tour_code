import { api } from './axios';

export interface TourPackageSummary {
  id: string;
  sheet_name: string;
  date_start: string;
  date_end: string;
  route: string;
  departure_city: string;
  pilgrims_count: number;
  created_at: string;
}

export interface TourPackageListResponse {
  items: TourPackageSummary[];
  total: number;
}

export interface MatchedPilgrimRow {
  id: string;
  surname: string;
  name: string;
  document: string;
  package_name: string;
  tour_code: string;
}

export interface ComparePilgrimRow {
  surname: string;
  name: string;
  document: string;
  package_name: string;
  tour_name: string;
}

export interface TourPackageDetailResponse {
  id: string;
  spreadsheet_id: string;
  spreadsheet_name: string;
  sheet_name: string;
  date_start: string;
  date_end: string;
  days: number;
  route: string;
  departure_city: string;
  country: string;
  hotel: string;
  remark: string;
  manifest_filename: string;
  dispatch_overrides: {
    filialid: string;
    firmid: string;
    firmname: string;
    q_touragent: string;
    q_touragent_bin: string;
  };
  matched: MatchedPilgrimRow[];
  in_sheet_not_in_manifest: ComparePilgrimRow[];
  in_manifest_not_in_sheet: ComparePilgrimRow[];
}

export interface AddTourPilgrimPayload {
  full_name: string;
  document?: string;
  package_name?: string;
}

export const listTourPackages = async (): Promise<TourPackageListResponse> => {
  const response = await api.get<TourPackageListResponse>('/api/v1/tour-packages');
  return response.data;
};

export const getTourPackage = async (tourId: string): Promise<TourPackageDetailResponse> => {
  const response = await api.get<TourPackageDetailResponse>(`/api/v1/tour-packages/${tourId}`);
  return response.data;
};

export const addTourPackagePilgrim = async (
  tourId: string,
  payload: AddTourPilgrimPayload
): Promise<MatchedPilgrimRow> => {
  const response = await api.post<MatchedPilgrimRow>(`/api/v1/tour-packages/${tourId}/pilgrims`, payload);
  return response.data;
};
