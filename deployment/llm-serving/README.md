# LLM Inference Service Deployment

This directory contains deployment configurations for LLM inference services. The default configuration utilizes HPU (Habana Gaudi) acceleration with vLLM as the inference engine.

## Service Components

The deployment will cover:

**vllm-gaudi-server**: The core inference engine service
- Runs on Habana Gaudi HPU
- Handles the actual model execution and inference
- Based on vLLM engine optimized for Gaudi

## Deployment Steps

0. In the corresponding docker-compose dir, copy ```env.example``` to ```.env``` at first.
1. Ensure your environment has Habana Gaudi HPU properly configured in the ```.env``` file.
2. Deploy the services using either Docker Compose or Helm Charts (configuration files provided in respective directories)
3. Verify both services are running and healthy

## Service Initialization

> **Important:** The LLM service initialization process may take several minutes due to model loading and optimization. Please verify the service status before proceeding:

### For Docker Compose Deployment
```bash
# Check container status
docker ps | grep vllm-gaudi-server

# Monitor initialization progress
docker logs -f vllm-gaudi-server
```

### For Kubernetes Deployment
```bash
# Check pod status
kubectl get pods -n <namespace> | grep vllm-gaudi-server

# Monitor initialization progress
kubectl logs -f <vllm-pod-name> -n <namespace>
```

## Service Architecture

```
Knowledge Base Components
        ↓
llm-vllm-gaudi-server (Adapter)
        ↓
  vllm-gaudi-server (Engine)
        ↓
    Habana Gaudi HPU
```

> **Note:** If you need to deploy on different hardware (e.g., CPU or GPU), please modify the corresponding configuration files and use appropriate container images. 
