# Financial News & Report Sentiment Analyzer for Market Intelligence

An intelligent system for financial decision making that analyzes news sentiment, social media buzz, and market data to provide comprehensive market intelligence.

## Features

- **FinBERT Sentiment Analysis** — GPU-accelerated financial sentiment classification (positive / negative / neutral) with confidence scores
- **Multi-Source News Collection** — Automated collection from Google News and Yahoo Finance on a Celery beat schedule
- **X (Twitter) Social Sentiment** — Stock buzz scores, bullish/bearish ratios, and trending tickers via the Adanos API
- **Market Data Integration** — Stock price and volume data from Yahoo Finance with sentiment–market correlation analysis
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
- API Keys:
  - **Groq** — Free at [console.groq.com](https://console.groq.com)
  - **Adanos** — Free tier at [adanos.org](https://adanos.org)
  - **Google News** (optional) — for Google News coverage

## Quick Start

1. **Clone and configure**
   ```bash
   git clone <repository-url>
   cd financial-sentiment-analyzer
   cp .env.example .env
   # Edit .env with your API keys
   ```

2. **Start all services**
   ```bash
   docker compose up --build
   ```

3. **Run database migrations**
   ```bash
   docker compose exec backend alembic upgrade head
   ```

4. **Access the application**
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
│   ├─ Sentiment Charts  │   ├─ FinBERT Analyzer (GPU)       │
│   ├─ Social Panel      │   ├─ Market Data (Yahoo Finance)  │
│   ├─ News Feed         │   ├─ Social Sentiment (Adanos)    │
│   ├─ Chat (Groq SSE)   │   ├─ Correlation Calculator       │
│   └─ Model Management  │   ├─ RAG Chat (Groq + ChromaDB)   │
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
| `ADANOS_API_KEY` | Adanos X sentiment API key | Yes |
| `GOOGLE_NEWS_API_KEY` | Google News API key | No |
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

```bash
# Create new migration
alembic revision --autogenerate -m "description"

# Apply migrations
alembic upgrade head

# Rollback
alembic downgrade -1
```

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
#   f i n a n c i a l - s e n t i m e n t - a n a l y s e r  
 