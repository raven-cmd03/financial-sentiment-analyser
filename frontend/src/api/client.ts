import axios, { AxiosError } from "axios";
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

api.interceptors.response.use(
  (response) => response,
  (error: AxiosError<{ detail?: string }>) => {
    const message =
      error.response?.data?.detail ||
      error.message ||
      "An unexpected error occurred";
    console.error(`[API Error] ${error.config?.method?.toUpperCase()} ${error.config?.url}: ${message}`);
    return Promise.reject(new Error(message));
  },
);

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
    // Backend returns 404 when a ticker has no social sentiment rows yet — treat as empty.
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
  const { data } = await api.post<DatasetInfo>("/finetuning/datasets/upload", formData, {
    headers: { "Content-Type": "multipart/form-data" },
  });
  return data;
}

interface FinetuningParams {
  dataset_name: string;
  hyperparams?: Record<string, unknown>;
}

export async function startFinetuning(
  params: FinetuningParams,
): Promise<FinetuningJob> {
  const { data } = await api.post<FinetuningJob>(
    "/finetuning/jobs",
    params,
  );
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
  const { data } = await api.post<ModelInfo>(`/finetuning/models/${id}/activate`);
  return data;
}
