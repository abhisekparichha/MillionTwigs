# MillionTwigs — Docker image for Render / Railway / Google Cloud Run
# Build: docker build -t milliontwigs .
# Run:   docker run -p 8501:8501 milliontwigs

FROM python:3.11-slim

WORKDIR /app

# Install only what the demo needs (no GDAL, no system libs required)
COPY requirements-demo.txt .
RUN pip install --no-cache-dir -r requirements-demo.txt

# Copy application code
COPY app.py .
COPY src/ src/
COPY config.yaml .

# Streamlit configuration
ENV STREAMLIT_SERVER_PORT=8501
ENV STREAMLIT_SERVER_ADDRESS=0.0.0.0
ENV STREAMLIT_SERVER_HEADLESS=true
ENV STREAMLIT_BROWSER_GATHER_USAGE_STATS=false

EXPOSE 8501

HEALTHCHECK CMD curl --fail http://localhost:8501/_stcore/health || exit 1

CMD ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]
