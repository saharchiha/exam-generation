# 🎓 Adaptive RAG — Tunisian Baccalaureate Exam Generator

An intelligent exam generation system powered by **Adaptive RAG (Retrieval-Augmented Generation)** with **Self-Reflection**, designed to automatically generate authentic Tunisian Baccalaureate exam exercises.

---

## 📌 Overview

This system uses a **parallel adaptive retrieval pipeline** to generate high-quality Bac exercises. Three sources are queried simultaneously and the best result (highest confidence score) feeds the LLM generation.

**Supported subjects:** Mathematics, Physics, Chemistry, Biology, History, Geography, Languages
**Supported languages:** French, Arabic, English
**Exam types:** Devoir de Contrôle / Devoir de Synthèse

---

## 🏗️ Architecture — Adaptive RAG + Self-Reflection

```
User Request (FastAPI)
        │
        ▼
EnhancedRAGGenerator (rag_gen.py)
        │
        ▼ 3 sources run IN PARALLEL (ThreadPoolExecutor)
┌───────────────┬───────────────┬───────────────┐
│  Weaviate RAG │  Web Search   │  Direct LLM   │
│  retriever.py │  enhanced_    │  (baseline    │
│               │  bac_search   │   conf: 0.4)  │
│  conf: 0-0.95 │  conf: 0-0.85 │               │
└───────┬───────┴───────┬───────┴───────┬───────┘
        │               │               │
        └───────────────┴───────────────┘
                        │
                 Best confidence wins
                        │
                        ▼
              LLM generates exercise
              (GPT-4o via OpenRouter)
                        │
                        ▼
              Self-Reflection (reflection.py)
              validates output quality
                        │
                        ▼
              Structured Exam Exercise (JSON)
                        │
                        ▼
              PDF / Text export (main.py)
```

### Confidence Scoring

| Source | Confidence Score |
|---|---|
| Weaviate RAG | certainty score + doc count bonus (max 0.95) |
| Web Search | source trust score (max 0.85) |
| Direct LLM | 0.4 baseline (no context) |

The source with the **highest confidence score** wins and its context feeds the LLM.

---

## 📁 Project Structure

```
EXAM-GENERATION/
├── app/
│   └── main.py                       # FastAPI entry point + PDF generation
├── embeddings/
│   ├── embedder.py                   # MiniLM sentence embeddings
│   ├── indexer_weaviate.py           # Weaviate batch indexer
│   └── processor.py                  # chunk → embed → index pipeline
├── generation/
│   ├── rag_gen.py                    # ⭐ Main pipeline orchestrator (Adaptive RAG)
│   └── enhanced_bac_search.py        # Web search — real Tunisian Bac exams
├── retrieval/
│   ├── retriever.py                  # Weaviate semantic search
│   └── reflection.py                 # Self-Reflection & quality validation
├── data/
│   ├── sc.py                         # Chunk balancing & cleaning
│   ├── semantic_chunking.py          # Semantic chunking with LangChain
│   └── metadata_extractor.py         # Metadata extraction from exam texts
├── react/
│   └── src/
│       ├── App.jsx                   # React root component
│       └── main.jsx                  # React entry point
├── test.py                           # Integration tests
├── requirements.txt                  # Python dependencies
├── .env.example                      # Environment variables template
└── README.md
```

---

## ⚙️ Setup & Installation

### Prerequisites

- Python 3.10+
- Node.js 18+
- [Docker](https://www.docker.com/) (for Weaviate)

### 1. Clone the repository

```bash
git clone https://github.com/saharchiha/exam-generation.git
cd exam-generation
```

### 2. Create virtual environment

```bash
python -m venv .venv

# Windows
.venv\Scripts\activate

# Linux / macOS
source .venv/bin/activate
```

### 3. Install Python dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure environment variables

```bash
cp .env.example .env
```

Edit `.env` with your actual keys:

```env
OPENROUTER_API_KEY=your_openrouter_key
GOOGLE_API_KEY=your_google_api_key
GOOGLE_CX=your_custom_search_engine_id
OPENAI_API_KEY=your_openai_key
LANGCHAIN_API_KEY=your_langsmith_key
WEAVIATE_URL=http://localhost:8080
```

### 5. Start Weaviate with Docker

```bash
docker run -d \
  --name weaviate \
  -p 8080:8080 \
  semitechnologies/weaviate:latest
```

### 6. Install React frontend

```bash
cd react
npm install
npm run dev
```

---

## 🚀 Running the Pipeline

### Step 1 — Prepare exam data

```bash
# Semantic chunking
python data/semantic_chunking.py

# Balance and clean chunks
python data/sc.py
```

### Step 2 — Embed & Index to Weaviate

```bash
python embeddings/processor.py
```

Runs: metadata extraction → MiniLM embedding → Weaviate indexing.

### Step 3 — Start the API

```bash
python app/main.py
```

API available at `http://localhost:8000`
Swagger docs at `http://localhost:8000/docs`

---

## 🔍 Key Modules

### `generation/rag_gen.py` — Pipeline Orchestrator
The core of the system. Runs 3 retrieval sources in parallel, selects the best by confidence score, generates the exercise with LLM, then applies self-reflection.

### `retrieval/retriever.py` — Weaviate RAG
Performs real semantic search using MiniLM embeddings with progressive filter relaxation (subject + language → subject only → no filters).

### `generation/enhanced_bac_search.py` — Web Search
Searches real Tunisian Baccalaureate exams from trusted sources (`devoir.tn`, `bacweb.tn`, `education.gov.tn`) using Google Custom Search API.

### `retrieval/reflection.py` — Self-Reflection
Validates generated exercise quality, checks factual accuracy against context, and computes a weighted confidence score (quality 40% + accuracy 30% + retrieval 30%).

---

## 📊 Example API Request

```bash
POST /api/generate-exam
{
  "field": "sciences",
  "subject": "mathématiques",
  "language": "french",
  "type": "controle",
  "session": "principale",
  "difficulty": "medium",
  "num_questions": 3,
  "lycee": "Lycée Pilote Sousse",
  "professeur": "Prof. Ben Ali"
}
```

### Example Response

```json
{
  "exam_id": "uuid-here",
  "status": "success",
  "exam_content": {
    "exercises": [
      {
        "exercise_number": 1,
        "text": "Exercice 1: Étude de fonction (5 points)\n\n1.a) ...\n1.b) ...",
        "points": 5,
        "correction": "1.a) Solution détaillée...",
        "confidence": 0.87,
        "context_source": "weaviate_rag"
      }
    ]
  }
}
```

---

## 🛠️ Tech Stack

| Layer | Technology |
|---|---|
| LLM | GPT-4o via OpenRouter |
| Embeddings | `all-MiniLM-L12-v2` (SentenceTransformers) |
| Vector DB | Weaviate |
| Web Search | Google Custom Search + BeautifulSoup |
| Self-Reflection | LangChain + Custom Validator |
| Backend | FastAPI (Python) |
| Frontend | React + Vite |
| PDF Export | ReportLab |

---

## 🧪 Testing

```bash
# Run integration tests
python test.py

# Verify Weaviate connection
python embeddings/check.py
```


## 👩‍💻 Author

**Sahar Chiha** — Tunisian Baccalaureate AI Exam Generator
[github.com/saharchiha](https://github.com/saharchiha)
