FROM python:3.12-slim AS builder

WORKDIR /build
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt numpy

COPY app/ app/

# Copy ALL pre-built data files (avoids slow API re-fetching during build)
COPY data/ data/

# Build arg for data.gov.in API key (only needed if data files don't exist)
ARG DATA_GOV_API_KEY=""
ENV DATA_GOV_API_KEY=${DATA_GOV_API_KEY}

# Regenerate risk_table and hb_trajectories (fast, no API needed).
# Skip facility_graph and real_facilities if pre-built data already exists.
RUN python -m app.precompute.generate_risk_table && \
    python -m app.precompute.generate_hb_trajectories && \
    if [ ! -f data/facility_graph.json ]; then \
        python -m app.precompute.generate_facility_graph; \
    else \
        echo "Using pre-built facility_graph.json"; \
    fi && \
    if [ ! -f data/real_facilities.json ]; then \
        python -m app.precompute.generate_real_facilities; \
    else \
        echo "Using pre-built real_facilities.json"; \
    fi

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
