import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import type {
  Company,
  CompanySentiment,
  NewsArticle,
  SocialSentiment,
} from "@/types";

// Mock the API client before importing the component so the component picks up
// the mocks via hoisting.
vi.mock("@/api/client", () => ({
  getCompany: vi.fn(),
  getCompanySentiment: vi.fn(),
  getNewsByTicker: vi.fn(),
  getSocialSentiment: vi.fn(),
}));

// Charts & correlation table make network calls we don't care about in this test.
vi.mock("@/components/SentimentChart/SentimentChart", () => ({
  default: () => <div data-testid="sentiment-chart" />,
}));
vi.mock("@/components/PriceChart/PriceChart", () => ({
  default: () => <div data-testid="price-chart" />,
}));
vi.mock("@/components/CorrelationTable/CorrelationTable", () => ({
  default: () => <div data-testid="correlation-table" />,
}));

import CompanyDetailPage from "@/pages/CompanyDetailPage";
import * as client from "@/api/client";

const mockedClient = client as unknown as {
  getCompany: ReturnType<typeof vi.fn>;
  getCompanySentiment: ReturnType<typeof vi.fn>;
  getNewsByTicker: ReturnType<typeof vi.fn>;
  getSocialSentiment: ReturnType<typeof vi.fn>;
};

const company: Company = {
  id: 1,
  ticker: "AAPL",
  name: "Apple Inc.",
  sector: "Technology",
  industry: "Consumer Electronics",
};

const sentiment: CompanySentiment = {
  company,
  overall_sentiment: "positive",
  overall_score: 0.42,
  average_positive: 0.61,
  average_negative: 0.19,
  average_neutral: 0.2,
  article_count: 87,
  trending: "up",
  recent_articles: [],
  social: null,
};

const article: NewsArticle = {
  article_id: "hash-1",
  title: "Apple beats earnings",
  content: "Strong quarter ...",
  source: "Reuters",
  url: "https://example.com/a",
  publication_date: "2025-01-01T00:00:00Z",
  sentiment: {
    result_id: 1,
    article_id: "hash-1",
    sentiment_label: "positive",
    positive_score: 0.8,
    negative_score: 0.1,
    neutral_score: 0.1,
    confidence: 0.8,
  },
};

const social: SocialSentiment = {
  id: 1,
  ticker_symbol: "AAPL",
  buzz_score: 72.5,
  bullish_ratio: 0.7,
  bearish_ratio: 0.2,
  post_volume: 1234,
  sentiment_trend: "up",
  fetched_at: "2025-01-01T00:00:00Z",
};

function renderPage() {
  return render(
    <MemoryRouter initialEntries={["/companies/AAPL"]}>
      <Routes>
        <Route path="/companies/:ticker" element={<CompanyDetailPage />} />
      </Routes>
    </MemoryRouter>,
  );
}

describe("CompanyDetailPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockedClient.getCompany.mockResolvedValue(company);
    mockedClient.getCompanySentiment.mockResolvedValue(sentiment);
    mockedClient.getNewsByTicker.mockResolvedValue([article]);
    mockedClient.getSocialSentiment.mockResolvedValue(social);
  });

  it("renders hero KPIs, social, and recent news from the API", async () => {
    renderPage();

    await waitFor(() => {
      expect(screen.getByText("Apple Inc.")).toBeInTheDocument();
    });

    // Overall score is rendered as a signed percentage.
    expect(screen.getByText(/\+42\.0/)).toBeInTheDocument();
    // Article count KPI.
    expect(screen.getByText("87")).toBeInTheDocument();
    // Social card present.
    expect(screen.getByText(/X \/ Social/i)).toBeInTheDocument();
    expect(screen.getByText(/1234 posts/)).toBeInTheDocument();
    // News article rendered using article_id as key (test by content).
    expect(screen.getByText("Apple beats earnings")).toBeInTheDocument();
  });

  it("renders an empty state when there's no social data", async () => {
    mockedClient.getSocialSentiment.mockResolvedValue(null);
    renderPage();

    await waitFor(() => {
      expect(screen.getByText("Apple Inc.")).toBeInTheDocument();
    });

    expect(screen.getByText(/No social data yet/i)).toBeInTheDocument();
  });
});
