# Use JuiceFS on Kubernetes

Author: yuhan.yang@intel.com

Update date: 02/05/2025

This document is a quick-start guide to set up and use [JuiceFS](https://juicefs.com/docs/community/introduction/) as storage backend for EKBA.

## Prerequisite
- A volume, at least 500G for storage
- A kubernetes cluster

## Installation steps
### Install JuiceFS file system
The JuiceFS file system is driven by both "Object Storage" and "Database".  The following shows the steps to set up a standalone mode JuiceFS.

#### 1. Install JuiceFS client

```bash
# default installation path is /usr/local/bin
curl -sSL https://d.juicefs.com/install | sh -
```
Details see: https://juicefs.com/docs/community/getting-started/installation

#### 2. Set up Metadata engine
Use redis as the metadata engine
```bash
# start the redis server
sudo docker run -d \
  --name redis \
  -p 6379:6379 \
  --restart unless-stopped \
  -v $HOST_PATH:/data \
  redis:latest \
  --requirepass "redisadmin"
```
[redis setup reference](https://juicefs.com/docs/community/databases_for_metadata)

#### 3. Set up object storage
Use minio as the object storage
```bash
# run a MinIO instance locally using docker
sudo docker run -d --name minio \
    -p 9000:9000 \
    -p 9900:9900 \
    -e "MINIO_ROOT_USER=minioadmin" \
    -e "MINIO_ROOT_PASSWORD=minioadmin" \
    -v $HOST_PATH:/data \
    --restart unless-stopped \
    minio/minio server /data --console-address ":9900"
```

[MinIO setup reference](https://juicefs.com/docs/community/reference/how_to_set_up_object_storage/#minio)

#### 4. Create a file system
```bash
# juicefs format [command options] META-URL NAME
juicefs format \
    --storage minio \
    --bucket http://${host_ip}:9000/ekba \
    --access-key minioadmin \
    --secret-key minioadmin \
    "redis://:${redis_password}@${host_ip}/1" \
    ekba
```

#### 5. Mount the file system (optional)
```bash
export LOCAL_MOUNT_PATH=~/jfs
juicefs mount -d "redis://:${redis_password}@${host_ip}:6379/1" ${LOCAL_MOUNT_PATH}

# to show
df -h
Filesystem                 Size  Used Avail Use% Mounted on
JuiceFS:ekba               1.0P   29G  1.0P   1% /home/sdp/jfs

# umount
juicefs umount ~/jfs
```

### Use JuiceFS on Kubernetes
JuiceFS is an ideal storage layer for Kubernetes. It supports two ways.

- [hostPath](https://juicefs.com/docs/community/how_to_use_on_kubernetes#use-juicefs-via-hostpath)
- [CSI Driver](https://juicefs.com/docs/community/how_to_use_on_kubernetes#juicefs-csi-driver)

The following is a simple guide to use JuiceFS CSI **dynamic provision** on Kubernetes
#### 1. JuiceFS CSI Driver Installation

Add the Helm repo, and then create a values file to store your cluster-specific configs
```bash
helm repo add juicefs https://juicedata.github.io/charts/
helm repo update

mkdir juicefs-csi-driver && cd juicefs-csi-driver

vim values-mycluster.yaml
```
`values-mycluster.yaml` can be downloaded from https://github.com/juicedata/charts/blob/main/charts/juicefs-csi-driver/values.yaml

Execute below commands to deploy JuiceFS CSI Driver:
```bash
# Use this command for both initial installation, and subsequent config changes
helm upgrade --install juicefs-csi-driver juicefs/juicefs-csi-driver -n juicefs-csi -f ./values-mycluster.yaml

$ kubectl get pod  -n juicefs-csi
NAME                                                                   READY   STATUS     RESTARTS      AGE
juicefs-csi-controller-0                                               3/3     Running    0             3h1m
juicefs-csi-controller-1                                               3/3     Running    0             179m
juicefs-csi-dashboard-69f75b6fcb-gfssk                                 1/1     Running    0             3h1m
juicefs-csi-node-6nj5b                                                 3/3     Running    0             3h1m
juicefs-csi-node-fccsm                                                 3/3     Running    0             3h1m
juicefs-gnr-server05-pvc-fd83b4b7-8f66-4d59-8d55-9a94bca2114b-kodbxd   1/1     Running    0             111m

```
[CSI driver installation reference](https://juicefs.com/docs/csi/getting_started#helm)

#### 2. Create and use PV
In JuiceFS, a Volume is a file system. With JuiceFS CSI Driver, Volume credentials are stored inside a Kubernetes Secret. We are using **community edition**.

##### Create kubernetes secret:
```yaml
apiVersion: v1
kind: Secret
metadata:
  name: juicefs-secret
  namespace: juicefs-csi
  labels:
    # Add this label to enable secret validation
    juicefs.com/validate-secret: "true"
type: Opaque
stringData:
  name: juicefs-vol
  metaurl: redis://:redisadmin@${host_ip}:6379/1
  storage: minio
  bucket: http://${host_ip}:9000/ekba
  access-key: minioadmin
  secret-key: minioadmin
```
To apply
```bash
kubectl apply -f secret.yaml
kubectl get secret -n juicefs-csi
NAME                                                      TYPE                 DATA   AGE
juicefs-secret                                            Opaque               6      179m

```

##### Create StorageClass via kubectl
```yaml
apiVersion: storage.k8s.io/v1
kind: StorageClass
metadata:
  name: juicefs-sc
provisioner: csi.juicefs.com
parameters:
  csi.storage.k8s.io/provisioner-secret-name: juicefs-secret
  csi.storage.k8s.io/provisioner-secret-namespace: juicefs-csi
  csi.storage.k8s.io/node-publish-secret-name: juicefs-secret
  csi.storage.k8s.io/node-publish-secret-namespace: juicefs-csi
reclaimPolicy: Retain
```
To apply
```bash
kubectl apply -f storageclass.yaml
kubectl get sc
NAME                        PROVISIONER       RECLAIMPOLICY   VOLUMEBINDINGMODE   ALLOWVOLUMEEXPANSION   AGE
juicefs-sc                  csi.juicefs.com   Delete          Immediate           false                  155m
```

##### Create PVC and example Pod:
reference : https://juicefs.com/docs/csi/guide/pv#dynamic-provisioning