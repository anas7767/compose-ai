export type UUID = string;
export type ISODateTime = string;

export interface PaginationMeta {
  nextCursor: string | null;
  hasMore: boolean;
  limit: number;
}

export interface ApiMeta {
  requestId: string;
  pagination?: PaginationMeta;
  warnings?: string[];
}

export interface ApiEnvelope<TData> {
  data: TData;
  meta: ApiMeta;
}

export interface FieldError {
  field: string;
  message: string;
  code: string;
}

export interface ApiErrorBody {
  code: string;
  message: string;
  details?: Record<string, unknown>;
  fieldErrors?: FieldError[];
  requestId: string;
  retryable: boolean;
}
