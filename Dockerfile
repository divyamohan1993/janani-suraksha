FROM python:3.12-slim AS builder

WORKDIR /build
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ app/
COPY data/real_facilities*.json data/
COPY data/learned_index_weights.json data/

# Build arg for data.gov.in API key (used only during precompute, not baked into runtime image)
ARG DATA_GOV_API_KEY=""
ENV DATA_GOV_API_KEY=${DATA_GOV_API_KEY}

# Precompute O(1) tables and fetch real facility data (baked into image)
RUN mkdir -p data && \
    python -m app.precompute.generate_risk_table && \
    python -m app.precompute.generate_facility_graph && \
    python -m app.precompute.generate_hb_trajectories && \
    python -m app.precompute.generate_real_facilities

FROM python:3.12-slim

# Defense in depth: non-root user
RUN groupadd -r janani && useradd -r -g janani -d /app -s /sbin/nologin janani

WORKDIR /app

COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin/uvicorn /usr/local/bin/uvicorn
COPY --from=builder /build/app ./app
COPY --from=builder /build/data ./data
COPY .env* ./

# Defense in depth: read-only filesystem where possible
RUN chown -R janani:janani /app

USER janani

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8080/api/v1/health')" || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080", "--workers", "1", "--log-level", "info"]
