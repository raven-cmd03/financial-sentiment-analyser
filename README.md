# Financial News & Report Sentiment Analyzer for Market Intelligence

An intelligent system for financial decision making that analyzes news sentiment, social media buzz, and market data to provide comprehensive market intelligence.

## Features

- **FinBERT Sentiment Analysis** — GPU-accelerated financial sentiment classification (positive / negative / neutral) with confidence scores
- **Multi-Source News Collection** — Automated ingestion from Google News RSS, Yahoo Finance, and Alpha Vantage `NEWS_SENTIMENT` on a Celery beat schedule, with URL-based deduplication across sources
- **X (Twitter) Social Sentiment** — Stock buzz scores, bullish/bearish ratios, and trending tickers via the Adanos API
- **Market Data Integration** — Daily OHLCV via Alpha Vantage `TIME_SERIES_DAILY` with a yfinance fallback, upserted nightly and chained off news collection so correlations always align on fresh prices
- **Statistical Correlations** — Pearson, Spearman, time-lagged, and rolling 7-day correlation calculations
- **Groq-Powered RAG Chat** — Ask questions about any stock with context from news, sentiment, and social data (Llama 3.3 70B Versatile)
- **FinBERT Fine-Tuning** — Train custom sentiment models on Financial PhraseBank or the zeroshot Twitter financial-news dataset using your GPU
- **Interactive Dashboard** — Charts, news feed, social sentiment panels, and CSV export

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python, FastAPI, SQLAlchemy, Celery |
| Frontend | React 18, TypeScript, Tailwind CSS, Recharts |
| ML/NLP | FinBERT (PyTorch), spaCy, Hugging Face Transformers |
| LLM | Groq API (Llama 3.3 70B), LangChain |
| Vector Store | ChromaDB with sentence-transformers embeddings |
| Database | PostgreSQL 16 |
| Cache/Queue | Redis 7 |
| Infrastructure | Docker Compose, Nginx, NVIDIA CUDA |

## Prerequisites

- Docker and Docker Compose
- NVIDIA GPU with CUDA support + [NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/install-guide.html)
- API keys (all free tiers):
  - **Groq** — [console.groq.com](https://console.groq.com) — required for RAG chat
  - **Alpha Vantage** — [alphavantage.co/support/#api-key](https://www.alphavantage.co/support/#api-key) — optional but recommended (news + prices)
  - **Adanos** — [adanos.org](https://adanos.org) — optional; social-sentiment panels no-op without it
  - **Google News RSS** — no key required

## Quick Start

1. **Clone and configure**
   ```bash
   git clone <repository-url>
   cd financial-sentiment-analyzer
   cp .env.example .env
   # Fill in POSTGRES_PASSWORD, SECRET_KEY, API_KEY (=VITE_API_KEY), GROQ_API_KEY,
   # and any optional keys (ALPHA_VANTAGE_API_KEY, ADANOS_API_KEY).
   ```

2. **Bring the whole stack up**
   ```bash
   docker compose up --build
   ```
   That one command is the full install. On first boot the backend container
   runs `alembic upgrade head` inside its entrypoint, which creates every
   table and seeds ~20 tracked companies. Celery beat immediately starts
   scheduling news collection, market-data refresh, social polling, and
   vector-store indexing.

3. **Access the application**
   - Dashboard: [http://localhost:8080](http://localhost:8080)
   - API Docs: [http://localhost:8080/api/docs](http://localhost:8080/api/docs)
   - API Health: [http://localhost:8080/api/health](http://localhost:8080/api/health)

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     Nginx (Port 8080)                       │
├────────────────────────┬────────────────────────────────────┤
│   React Frontend       │        FastAPI Backend             │
│   (Port 3000)          │        (Port 8001)                 │
│                        │                                    │
│   ┌─ Dashboard         │   ┌─ News Collector (Celery)      │
│   ├─ Sentiment Charts  │   │   • Google News / Yahoo / AV  │
│   ├─ Price Charts (AV) │   ├─ FinBERT Analyzer (GPU)       │
│   ├─ Social Panel      │   ├─ Market Data (Alpha Vantage → │
│   ├─ News Feed         │   │   yfinance fallback)          │
│   ├─ Chat (Groq SSE)   │   ├─ Social Sentiment (Adanos)    │
│   └─ Model Management  │   ├─ Correlation Calculator       │
│                        │   ├─ RAG Chat (Groq + ChromaDB)   │
│                        │   └─ Fine-Tuning Pipeline         │
├────────────────────────┴────────────────────────────────────┤
│  PostgreSQL  │  Redis  │  ChromaDB  │  Celery Workers       │
└──────────────┴─────────┴────────────┴───────────────────────┘
```

## API Endpoints

### Companies
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/companies` | List all tracked companies |
| GET | `/api/companies/{ticker}` | Company details |
| GET | `/api/companies/{ticker}/sentiment` | Current sentiment analysis |
| GET | `/api/companies/{ticker}/sentiment/history` | Historical sentiment |
| GET | `/api/companies/{ticker}/market` | Daily OHLCV (Alpha Vantage primary, yfinance fallback) |

### News
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/news` | Recent news articles |
| GET | `/api/news/{ticker}` | Company-specific news |
| GET | `/api/news/article/{id}` | Article detail |

### Social Sentiment
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/social/{ticker}` | Current X sentiment |
| GET | `/api/social/{ticker}/history` | Historical X sentiment |
| GET | `/api/social/trending/top` | Top trending tickers |

### Trends & Correlations
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/trends` | Market-wide trends |
| GET | `/api/trends/{ticker}` | Company trends |
| GET | `/api/correlations/{ticker}` | Correlation data |

### Chat
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/chat/sessions` | Create chat session |
| GET | `/api/chat/sessions` | List sessions |
| POST | `/api/chat/sessions/{id}/messages` | Send message (SSE stream) |

### Fine-Tuning
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/finetuning/datasets` | Available datasets |
| POST | `/api/finetuning/jobs` | Start training job |
| GET | `/api/finetuning/jobs/{id}/stream` | Training progress (SSE) |
| POST | `/api/finetuning/models/{id}/activate` | Switch active model |

## Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `GROQ_API_KEY` | Groq API key for chat and agentic AI | Yes |
| `GROQ_MODEL` | Groq model name (default: `llama-3.3-70b-versatile`) | No |
| `ADANOS_API_KEY` | Adanos X sentiment API key | No (social panels empty without it) |
| `ALPHA_VANTAGE_API_KEY` | Alpha Vantage key (news + prices). Without it, news falls back to Google/Yahoo and prices to yfinance. | No (recommended) |
| `GOOGLE_NEWS_API_KEY` | Reserved for future Google News API use (RSS path needs no key) | No |
| `POSTGRES_USER` | Database username (default: `finsentiment`) | No |
| `POSTGRES_PASSWORD` | Database password | Yes (no default) |
| `POSTGRES_DB` | Database name (default: `finsentiment`) | No |
| `SECRET_KEY` | Application secret key (placeholder values are rejected) | Yes |
| `API_KEY` | Shared API key required by `/api/finetuning`, `/api/chat`, `/api/ws` | Yes |
| `VITE_API_KEY` | Frontend build-time copy of `API_KEY` | Yes |
| `CORS_ORIGINS` | Comma-separated list of allowed origins | No |

## Development

### Running without Docker

**Backend:**
```bash
cd backend
pip install -r requirements.txt
python -m spacy download en_core_web_sm
uvicorn app.main:app --reload --port 8000
```

**Frontend:**
```bash
cd frontend
npm install
npm run dev
```

**Celery worker:**
```bash
cd backend
celery -A app.workers.celery_app worker --loglevel=info
celery -A app.workers.celery_app beat --loglevel=info
```

### Database Migrations

Migrations run **automatically** on every `docker compose up` via the backend
container's entrypoint (`backend/docker-entrypoint.sh`). You only need these
commands when iterating on the schema locally:

```bash
# Create new migration
alembic revision --autogenerate -m "description"

# Apply migrations manually (no-op if already at head)
alembic upgrade head

# Rollback
alembic downgrade -1
```

### Alpha Vantage Integration

Alpha Vantage is wired into two independent subsystems:

1. **News ingestion** — `backend/app/clients/alpha_vantage.py::fetch_news` calls
   the `NEWS_SENTIMENT` endpoint. Results are normalized into the same shape
   as Google News / Yahoo Finance articles and deduplicated by URL before
   FinBERT scores them. Per-ticker sentiment from Alpha Vantage is captured
   as metadata (`provider_sentiment`) so downstream code can compare it
   against FinBERT's own output.
2. **Market data** — `fetch_daily_prices` (`TIME_SERIES_DAILY`) feeds the new
   `collect_market_data_task` Celery job. That task runs nightly (beat
   `16:30 UTC`) **and** is chained off `collect_news_task`, so every fresh
   news batch triggers a corresponding price refresh. If Alpha Vantage is
   rate-limited or unset, the task falls back to yfinance — the correlation
   engine never starves.

Free-tier quotas (5 req/min, 500 req/day) are enforced by the base client's
token-bucket rate limiter at `4 req/min` to keep a safety margin.

## Datasets for Fine-Tuning

| Dataset key | Hugging Face source | Labels |
|-------------|---------------------|--------|
| `financial_phrasebank` | `financial_phrasebank` (config `sentences_allagree`) | negative, neutral, positive |
| `fintweet-sentiment-2025` | `zeroshot/twitter-financial-news-sentiment` | bearish, bullish, neutral |
| Custom CSV | User upload (columns: `text,label`) | User-defined |

## Disclaimer

This system is designed for educational and research purposes. It provides correlational analysis between news sentiment and market movements — **not investment advice**. Financial markets are influenced by numerous factors beyond news sentiment. Always consult qualified financial advisors before making investment decisions.

## Team

- **Aaraiz Masood** — Team Lead
- **Syed Ammar Ali Zaidi** — Member
- **Syed Baryal Shah** — Member

**Supervisor:** Ma'am Samreen Kazi
**Department:** School of Mathematics and Computer Science, IBA
#   f i n a n c i a l - s e n t i m e n t - a n a l y s e r 
 
 