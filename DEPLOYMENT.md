# Streamlit Deployment Guide

## Local Testing

```bash
cd Benchmark/LLMPerformanceBenchmarkUI
streamlit run app.py
```

## Production Deployment

### Option 1: Streamlit Cloud (Recommended)

1. Push to GitHub
2. Visit [streamlit.io/cloud](https://streamlit.io/cloud)
3. Deploy from repository:
   - Select this repository
   - Branch: `main`
   - Path: `Benchmark/LLMPerformanceBenchmarkUI/app.py`

### Option 2: Docker

Create `Dockerfile`:

```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

EXPOSE 8501

CMD ["streamlit", "run", "Benchmark/LLMPerformanceBenchmarkUI/app.py"]
```

Build and run:

```bash
docker build -t llm-benchmark-ui .
docker run -p 8501:8501 llm-benchmark-ui
```

### Option 3: Heroku

```bash
git push heroku main
```

### Option 4: Self-hosted (Nginx + Gunicorn)

```bash
pip install -r requirements.txt
streamlit run Benchmark/LLMPerformanceBenchmarkUI/app.py --server.port 8501
```

Use Nginx as reverse proxy pointing to `localhost:8501`.

## Environment Variables

No secrets required for this app. All data is read from local files.

## File Structure for Deployment

```
├── requirements.txt          ✓
├── .streamlit/
│   ├── config.toml          ✓
│   └── .gitignore           ✓
└── Benchmark/
    └── LLMPerformanceBenchmarkUI/
        ├── app.py           ✓
        ├── results_*.jsonl
        └── datasetPerformance/
            ├── results_Wikipediatest.jsonl
            ├── results_KG-Gentest.jsonl
            └── results_PromptOpttest.jsonl
```

## Data Files

The app expects result files in:
- `Benchmark/results_*.jsonl` - Main benchmark results
- `Benchmark/datasetPerformance/` - Test dataset results

Make sure these files are included in deployment.
