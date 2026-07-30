# How to Run

## Prerequisites
1. External llm service up and running.(By default we didn't bringup llm inference service and depends on an external one)
2. Kubernetes cluster support dynamic volume provisioning.
3. You should have Helm (version >= 3.15) installed if you want to deploy with Helm Charts.

## Steps to deploy with kubernetes

### Create NS to deploy ekba

```
export NS=ekba
kubectl create ns $NS
```

### Create PVC for model cache and data files

```
cat > pvc.yaml << EOF
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: datafiles
spec:
  accessModes:
    - ReadWriteMany
  resources:
    requests:
      storage: 10Gi
---
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: opea-models
spec:
  accessModes:
    - ReadWriteMany
  resources:
    requests:
      storage: 500Gi
---
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: mongo-db
spec:
  accessModes:
    - ReadWriteMany
  resources:
    requests:
      storage: 100Gi

EOF

kubectl -n $NS apply -f pvc.yaml
```

Note: You might need to access the PVC to make it really provisioned.

Use the following test pod to access the PVC:

```
cat >testpod.yaml <<EOF
apiVersion: v1
kind: Pod
metadata:
  name: test-pod
spec:
  containers:
  - name: test-container
    image: nginx
    volumeMounts:
    - name: datafiles
      mountPath: /data
    - name: opea-models
      mountPath: /weight
    - name: mongo-db
      mountPath: /mongo-db
  volumes:
  - name: opea-models
    persistentVolumeClaim:
      claimName: opea-models
  - name: datafiles
    persistentVolumeClaim:
      claimName: datafiles
  - name: mongo-db
    persistentVolumeClaim:
      claimName: mongo-db
EOF
```

#### Copy pre-converted model weights for OpenVINO embedding server

You can copy files from host or from container.

Note: you need to prepare `ovms.tar.gz` in advance.

`tar xvzf ovms.tar.gz -C /Path-To-Your-OPEA-Models-PVC`

### Deploy

`cd $sourceRepo`


#### Configure LLM ENDPOINT

```
# Create a llm-values.yaml file with your endpoint.
# Note: By default, `LLM_ENDPOINT` should point to your vLLM server endpoint.
# For Gaudi HPU setup, this would be http://<vllm-server-ip>:8008 if started from llm-serving/docker-compose/HPU directory
cat > llm-values.yaml <<EOF
llm-uservice:
  LLM_MODEL_ID: DeepSeek-R1-Distill-Qwen-32B
  LLM_ENDPOINT: http://${input-your-llm-ipaddress}:8001
EOF
```
#### Deploy ekba

```
# Update dependency
helm dependency update deployment/helm-charts/chatqna
# Deploy
helm -n $NS install ekba deployment/helm-charts/chatqna -f deployment/helm-charts/chatqna/ekba-values.yaml -f llm-values.yaml
```

### Verify Service Status

Check all resources status:
```bash
# Check all pods status
kubectl -n $NS get pods -o wide
# Ensure all pods are Running and Ready (e.g., 1/1, 2/2)

# Check all services status
kubectl -n $NS get svc
# Verify all services have cluster IPs and correct ports

# Check all deployments status
kubectl -n $NS get deployments
# Ensure all deployments show desired number of replicas available

# Check persistent volume claims
kubectl -n $NS get pvc
# Ensure PVCs are Bound

```

Wait until all resources are in ready state before proceeding with application usage.
