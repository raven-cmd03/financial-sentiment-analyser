import axios, { AxiosError } from "axios";
import { toast } from "sonner";
import type {
  Company,
  NewsArticle,
  CompanySentiment,
  TrendData,
  CorrelationData,
  SocialSentiment,
  ChatSession,
  ChatMessage,
  DatasetInfo,
  FinetuningJob,
  ModelInfo,
  MarketDataResponse,
} from "@/types";

const API_KEY = (import.meta.env.VITE_API_KEY as string | undefined) ?? "";

const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL || "/api",
  headers: {
    "Content-Type": "application/json",
    // Forwarded to every request; backend enforces on sensitive routes only.
    ...(API_KEY ? { "X-API-Key": API_KEY } : {}),
  },
  timeout: 30000,
});

export function getApiKey(): string {
  return API_KEY;
}

/**
 * Thrown when the backend returns 401/403 on a sensitive endpoint — i.e.
 * the server is running but `API_KEY` is empty or wrong. The UI catches
 * this specifically to show a gated-state banner instead of a red error.
 */
export class ApiLockedError extends Error {
  readonly status: number;
  constructor(status: number, message: string) {
    super(message);
    this.name = "ApiLockedError";
    this.status = status;
  }
}

interface ApiErrorPayload {
  detail?: string;
}

// Endpoints where a generic error toast would be spammy (the UI already
// surfaces these errors inline on the affected widgets).
const SILENT_ERROR_PATHS = ["/social/"];

function shouldBeSilent(url: string | undefined): boolean {
  if (!url) return false;
  return SILENT_ERROR_PATHS.some((p) => url.includes(p));
}

api.interceptors.response.use(
  (response) => response,
  (error: AxiosError<ApiErrorPayload>) => {
    const status = error.response?.status ?? 0;
    const detail = error.response?.data?.detail;
    const message =
      detail || error.message || "An unexpected error occurred";
    const url = error.config?.url;
    const method = error.config?.method?.toUpperCase();

    console.error(`[API Error] ${method} ${url}: ${status} ${message}`);

    // 401/403 = missing/invalid key. 503 with the "API_KEY is not configured"
    // detail is the backend's way of saying the gate is off entirely — same UX.
    const isKeyMissing503 =
      status === 503 && /api_key is not configured/i.test(message);

    if (status === 401 || status === 403 || isKeyMissing503) {
      return Promise.reject(new ApiLockedError(status, message));
    }

    // Only show toasts for actual server errors — the UI already handles
    // 404s inline (empty states) and 4xx coverage is noisy.
    if (status >= 500 && !shouldBeSilent(url)) {
      toast.error("Service error", {
        description: message,
      });
    }

    return Promise.reject(new Error(message));
  },
);

export function isLockedError(err: unknown): err is ApiLockedError {
  return err instanceof ApiLockedError;
}

// ── Status ─────────────────────────────────────────────────

export interface BackendStatus {
  service: string;
  groq_model: string;
  finbert_model: string;
  embedding_model: string;
}

export async function getBackendStatus(): Promise<BackendStatus> {
  const { data } = await api.get<BackendStatus>("/status");
  return data;
}

// ── Companies ──────────────────────────────────────────────

export async function getCompanies(): Promise<Company[]> {
  const { data } = await api.get<Company[]>("/companies");
  return data;
}

export async function getCompany(ticker: string): Promise<Company> {
  const { data } = await api.get<Company>(`/companies/${ticker}`);
  return data;
}

export async function getCompanySentiment(
  ticker: string,
): Promise<CompanySentiment> {
  const { data } = await api.get<CompanySentiment>(
    `/companies/${ticker}/sentiment`,
  );
  return data;
}

export async function getSentimentHistory(
  ticker: string,
  days = 30,
): Promise<TrendData[]> {
  const { data } = await api.get<TrendData[]>(
    `/companies/${ticker}/sentiment/history`,
    { params: { days } },
  );
  return data;
}

export async function getMarketData(
  ticker: string,
  days = 30,
): Promise<MarketDataResponse> {
  const { data } = await api.get<MarketDataResponse>(
    `/companies/${ticker}/market`,
    { params: { days } },
  );
  return data;
}

// ── News ───────────────────────────────────────────────────

interface NewsParams {
  page?: number;
  limit?: number;
  sentiment?: string;
  source?: string;
  start_date?: string;
  end_date?: string;
}

export async function getNews(params?: NewsParams): Promise<NewsArticle[]> {
  const { data } = await api.get<NewsArticle[]>("/news", { params });
  return data;
}

export async function getNewsByTicker(
  ticker: string,
  params?: NewsParams,
): Promise<NewsArticle[]> {
  const { data } = await api.get<NewsArticle[]>(`/news/${ticker}`, { params });
  return data;
}

export async function getArticle(id: string): Promise<NewsArticle> {
  const { data } = await api.get<NewsArticle>(`/news/article/${id}`);
  return data;
}

// ── Trends ─────────────────────────────────────────────────

export async function getTrends(days = 30): Promise<TrendData[]> {
  const { data } = await api.get<TrendData[]>("/trends", { params: { days } });
  return data;
}

export async function getTrendsByTicker(
  ticker: string,
): Promise<TrendData[]> {
  const { data } = await api.get<TrendData[]>(`/trends/${ticker}`);
  return data;
}

// ── Correlations ───────────────────────────────────────────

export async function getCorrelations(
  ticker: string,
): Promise<CorrelationData[]> {
  const { data } = await api.get<CorrelationData[]>(
    `/correlations/${ticker}`,
  );
  return data;
}

// ── Social Sentiment ───────────────────────────────────────

export async function getSocialSentiment(
  ticker: string,
): Promise<SocialSentiment | null> {
  try {
    const { data } = await api.get<SocialSentiment>(`/social/${ticker}`);
    return data;
  } catch (err) {
    if (isLockedError(err)) throw err;
    // Backend returns 404 when a ticker has no social sentiment rows yet.
    if ((err as Error).message?.includes("No social sentiment")) return null;
    throw err;
  }
}

export async function getSocialHistory(
  ticker: string,
  days = 30,
): Promise<SocialSentiment[]> {
  const { data } = await api.get<SocialSentiment[]>(
    `/social/${ticker}/history`,
    { params: { days } },
  );
  return data;
}

export async function getTrendingTickers(): Promise<SocialSentiment[]> {
  const { data } = await api.get<SocialSentiment[]>("/social/trending/top");
  return data;
}

// ── Chat ───────────────────────────────────────────────────

export async function createChatSession(
  title?: string,
): Promise<ChatSession> {
  const { data } = await api.post<ChatSession>("/chat/sessions", { title });
  return data;
}

export async function getChatSessions(): Promise<ChatSession[]> {
  const { data } = await api.get<ChatSession[]>("/chat/sessions");
  return data;
}

export async function getChatSession(
  id: string,
): Promise<{ session: ChatSession; messages: ChatMessage[] }> {
  const { data } = await api.get(`/chat/sessions/${id}`);
  return data;
}

export function sendChatMessageUrl(sessionId: string | number): string {
  const baseURL = import.meta.env.VITE_API_URL || "/api";
  return `${baseURL}/chat/sessions/${sessionId}/messages`;
}

export async function deleteChatSession(id: string): Promise<void> {
  await api.delete(`/chat/sessions/${id}`);
}

// ── Model Management ───────────────────────────────────────

export async function getDatasets(): Promise<DatasetInfo[]> {
  const { data } = await api.get<DatasetInfo[]>("/finetuning/datasets");
  return data;
}

export async function uploadDataset(file: File): Promise<DatasetInfo> {
  const formData = new FormData();
  formData.append("file", file);
  const { data } = await api.post<DatasetInfo>(
    "/finetuning/datasets/upload",
    formData,
    { headers: { "Content-Type": "multipart/form-data" } },
  );
  return data;
}

interface FinetuningParams {
  dataset_name: string;
  hyperparams?: Record<string, unknown>;
}

export async function startFinetuning(
  params: FinetuningParams,
): Promise<FinetuningJob> {
  const { data } = await api.post<FinetuningJob>("/finetuning/jobs", params);
  return data;
}

export async function getFinetuningJobs(): Promise<FinetuningJob[]> {
  const { data } = await api.get<FinetuningJob[]>("/finetuning/jobs");
  return data;
}

export async function getFinetuningJob(id: string): Promise<FinetuningJob> {
  const { data } = await api.get<FinetuningJob>(`/finetuning/jobs/${id}`);
  return data;
}

export async function getModels(): Promise<ModelInfo[]> {
  const { data } = await api.get<ModelInfo[]>("/finetuning/models");
  return data;
}

export async function activateModel(id: string): Promise<ModelInfo> {
  const { data } = await api.post<ModelInfo>(
    `/finetuning/models/${id}/activate`,
  );
  return data;
}
