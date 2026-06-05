# Crawl Microservice

This microservice is responsible for web crawling, data extraction, and processing for downstream applications.

## 🚀 Service Usage Guide

> **Note:** The examples below use `localhost` and specific ports applicable for Docker deployment. For Kubernetes deployment:
> 1. Get the service IP: `kubectl get svc -n <namespace>`
> 2. Replace `localhost` with the service IP in the commands below
> 3. Use the port exposed by the Kubernetes service

### 1. Start the Service

#### **Using Docker**
Run the following command to start the crawl service in a Docker container:
```bash
docker build -t crawl_service .

docker run -d \
  --name crawl_service \
  -p 7010:7010 \
  -v /tmp/craw/uploaded_files:/app/uploaded_files \
  crawl_service

# Ensure correct permissions
sudo chmod -R 777 /tmp/craw/uploaded_files
```

### 2. Crawling by links

You can send URLs to be crawled using a `POST` request:
```bash
curl --location 'http://localhost:7010/v1/crawlee/crawling' \
--form 'link_list="[\"https://github.com/intel-analytics/ipex-llm/blob/main/docs/mddocs/Quickstart/install_windows_gpu.md\"]"'
```

### 4. File Storage and Access

Crawled data is stored in `/app/uploaded_files` inside the container. If mounted to a host directory:
- Access files at `/tmp/craw/uploaded_files` on the host machine.
- Ensure proper permissions using:
  ```bash
  sudo chmod -R 777 /tmp/craw/uploaded_files
  ```

## 🔧 Configuration

Modify `crawler_config.json` for customization:
```json
{
  "crawler": {
    "max_depth": 2,
    "filters": [
      "https://github.com/intel-analytics/ipex-llm/**",
      "https://github.com/intel/ipex-llm/**",
      "https://github.com/openvinotoolkit/**",
      "https://github.com/intel/ipex-llm-tutorial/**",
      "https://github.com/intel/aog/**",
      "https://www.intel.com/content/**"
    ],
    "allowed_extensions": [".md", ".ipynb", ".html", ".htm"],
    "no_extension_pattern": "/[^./]*$",
    "max_retries": 3,
    "timeout_seconds": 60,
    "max_requests": 1000,
    "max_concurrency": 50,
    "max_tasks_per_minute": 200,
    "session_pool_size": 100
  }
}
```
or use environment variables:
```bash
export MAX_CONCURRENCY=50
export MAX_TASKS_PER_MINUTE=200
export MAX_RETRIES=3
export TIMEOUT_SECONDS=60
export MAX_REQUESTS=1000
export MAX_DEPTH=2
export SESSION_POOL_SIZE=100
export CRAWL_FILTERS=[ \
      "https://github.com/intel-analytics/ipex-llm/**",\
      "https://github.com/intel/ipex-llm/**",\
      "https://github.com/openvinotoolkit/**",\
      "https://github.com/intel/ipex-llm-tutorial/**",\
      "https://github.com/intel/aog/**",\
      "https://www.intel.com/content/**"\
    ]
```

## 📌 Notes
- Ensure that required dependencies (e.g., Playwright) are installed.
- For permission issues, ensure correct user mappings when running Docker/Kubernetes.

## 🛠 Troubleshooting

### **Playwright Issues**
If you encounter browser sandboxing issues, try disabling the sandbox:
```bash
ENV PLAYWRIGHT_BROWSERS_PATH="/home/app/.cache/ms-playwright"
playwright install --with-deps
chown -R 777 /home/app/.cache/ms-playwright
```