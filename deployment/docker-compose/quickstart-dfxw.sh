#!/usr/bin/env bash

# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

# Check command line argument
if [[ "$1" == "stop" ]]; then
    ACTION="stop"
else
    ACTION="start"
fi

# helper function to ask yes/no input
function asking() {
    local question=$1
    local default=Y
    [[ -n $2 ]] && default=$2

    while true; do
        read -p "$question (y/n) [$default]: " yn
        yn=${yn:-$default}  # use default value if no input
        case $yn in
            [Yy]* ) return 0;;
            [Nn]* ) return 1;;
            * ) echo "Please answer yes (y) or no (n).";;
        esac
    done
}

# helper function to choose one from list
_model_serving=""
function choose_one() {
    local question=$1
    local options=("${@:2}")
    echo "$question"
    for i in "${!options[@]}"; do
        echo "$((i+1)). ${options[$i]}"
    done
    # Ensure the prompt is visible by flushing stdout
    printf "\n"

    while true; do
        read -p "Enter the number of your choice [1]: " choice
        choice=${choice:-1}  # Set default value to 1 if no input
        if [[ "$choice" =~ ^[0-9]+$ ]] && ((choice >= 1 && choice <= ${#options[@]})); then
            _model_serving="${options[$((choice-1))]}"
            break
        else
            echo "Invalid choice, please try again."
        fi
    done
}

# detect the right dc cmd
export _DC_CMD
docker compose version >& /dev/null && _DC_CMD='docker compose'
[[ -z $_DC_CMD ]] && docker-compose version >& /dev/null && _DC_CMD='docker-compose'
[[ -z $_DC_CMD ]] && {
  echo "Need to install docker-compose package or upgrade docker cli to latest version"
  exit 1
}

LOCAL_IMAGE_REGISTRY="localhost:5000"

SOURCE_IMAGE_UI="${SOURCE_IMAGE_UI:-registry.cn-hangzhou.aliyuncs.com/jilimoxing/test:ui1.0}"
SOURCE_IMAGE_CHATHISTORY="${SOURCE_IMAGE_CHATHISTORY:-registry.cn-hangzhou.aliyuncs.com/jilimoxing/test:chathistory1.0}"
SOURCE_IMAGE_DATAPREP="${SOURCE_IMAGE_DATAPREP:-registry.cn-hangzhou.aliyuncs.com/jilimoxing/test:dataprep1.0}"
SOURCE_IMAGE_ACCOUNT="${SOURCE_IMAGE_ACCOUNT:-registry.cn-hangzhou.aliyuncs.com/jilimoxing/test:account1.0}"
SOURCE_IMAGE_SMART_PRACTICE="${SOURCE_IMAGE_SMART_PRACTICE:-registry.cn-hangzhou.aliyuncs.com/jilimoxing/test:smart-practice1.0}"
SOURCE_IMAGE_SYSTEM_COMMON="${SOURCE_IMAGE_SYSTEM_COMMON:-registry.cn-hangzhou.aliyuncs.com/jilimoxing/test:system-common1.0}"
SOURCE_IMAGE_LEARN="${SOURCE_IMAGE_LEARN:-registry.cn-hangzhou.aliyuncs.com/jilimoxing/test:learn1.0}"
SOURCE_IMAGE_ASR="${SOURCE_IMAGE_ASR:-registry.cn-hangzhou.aliyuncs.com/jilimoxing/test:asr1.0}"
SOURCE_IMAGE_EXCEL="${SOURCE_IMAGE_EXCEL:-registry.cn-hangzhou.aliyuncs.com/jilimoxing/test:excel1.0}"
SOURCE_IMAGE_DASHBOARD="${SOURCE_IMAGE_DASHBOARD:-registry.cn-hangzhou.aliyuncs.com/jilimoxing/test:dashboard1.0}"

SOURCE_IMAGE_MONGO="${SOURCE_IMAGE_MONGO:-registry.cn-hangzhou.aliyuncs.com/jilimoxing/test:mongo7.0.11}"
SOURCE_IMAGE_MYSQL="${SOURCE_IMAGE_MYSQL:-registry.cn-hangzhou.aliyuncs.com/jilimoxing/test:mysql8.0.39}"
SOURCE_IMAGE_REDIS="${SOURCE_IMAGE_REDIS:-registry.cn-hangzhou.aliyuncs.com/jilimoxing/test:redis8.0.2}"
SOURCE_IMAGE_MINIO="${SOURCE_IMAGE_MINIO:-registry.cn-hangzhou.aliyuncs.com/jilimoxing/test:minio1.0}"
SOURCE_IMAGE_ETCD="${SOURCE_IMAGE_ETCD:-registry.cn-hangzhou.aliyuncs.com/jilimoxing/test:etcd3.5.18}"
SOURCE_IMAGE_MILVUS="${SOURCE_IMAGE_MILVUS:-registry.cn-hangzhou.aliyuncs.com/jilimoxing/test:milvus2.5.10}"

function read_env_value() {
    local file=$1
    local key=$2
    local default_value=$3
    local value
    value=$(grep -E "^${key}=" "$file" 2>/dev/null | tail -n1 | cut -d'=' -f2-)
    value=${value%\"}
    value=${value#\"}
    if [ -z "$value" ]; then
        value=$default_value
    fi
    printf '%s' "$value"
}

function pull_and_tag_image() {
    local source_image=$1
    local target_image=$2

    if [ -z "$source_image" ] || [ -z "$target_image" ]; then
        return
    fi

    echo "Pulling $source_image"
    docker pull "$source_image"
    echo "Tagging $source_image as $target_image"
    docker tag "$source_image" "$target_image"
}

function prepare_images() {
    local dfxw_registry=$1
    local dfxw_tag=$2

    echo "Preparing practice images..."

    pull_and_tag_image "$SOURCE_IMAGE_UI" "${dfxw_registry}/ekba/ui:${dfxw_tag}"
    pull_and_tag_image "$SOURCE_IMAGE_CHATHISTORY" "${dfxw_registry}/ekba/chathistory:${dfxw_tag}"
    pull_and_tag_image "$SOURCE_IMAGE_DATAPREP" "${dfxw_registry}/ekba/dataprep:${dfxw_tag}"
    pull_and_tag_image "$SOURCE_IMAGE_ACCOUNT" "${dfxw_registry}/ekba/account:${dfxw_tag}"
    pull_and_tag_image "$SOURCE_IMAGE_SMART_PRACTICE" "${dfxw_registry}/ekba/smart-practice:${dfxw_tag}"
    pull_and_tag_image "$SOURCE_IMAGE_SYSTEM_COMMON" "${dfxw_registry}/ekba/system-common:${dfxw_tag}"
    pull_and_tag_image "$SOURCE_IMAGE_LEARN" "${dfxw_registry}/ekba/learn:${dfxw_tag}"
    pull_and_tag_image "$SOURCE_IMAGE_ASR" "${dfxw_registry}/ekba/asr:${dfxw_tag}"
    pull_and_tag_image "$SOURCE_IMAGE_EXCEL" "${dfxw_registry}/ekba/excel:${dfxw_tag}"
    pull_and_tag_image "$SOURCE_IMAGE_DASHBOARD" "${dfxw_registry}/ekba/dashboard:${dfxw_tag}"

    echo "Preparing backend images..."

    pull_and_tag_image "$SOURCE_IMAGE_MONGO" "mongo:7.0.11"
    pull_and_tag_image "$SOURCE_IMAGE_MYSQL" "mysql:8.0.39"
    pull_and_tag_image "$SOURCE_IMAGE_REDIS" "redis:8.0.2"
    pull_and_tag_image "$SOURCE_IMAGE_MINIO" "quay.io/minio/minio:RELEASE.2023-12-20T01-00-02Z"
    pull_and_tag_image "$SOURCE_IMAGE_ETCD" "quay.io/coreos/etcd:v3.5.18"
    pull_and_tag_image "$SOURCE_IMAGE_MILVUS" "milvusdb/milvus:v2.5.10"
}

function ensure_ui_tls_files() {
    local tls_dir="dfxw/nginx-ssl"
    local tls_crt="${tls_dir}/tls.crt"
    local tls_key="${tls_dir}/tls.key"

    mkdir -p "$tls_dir"

    if [ -f "$tls_crt" ] && [ -f "$tls_key" ]; then
        echo "Found existing UI TLS certificate files. Reusing them."
        return
    fi

    if ! command -v openssl >/dev/null 2>&1; then
        echo "openssl is required to generate UI TLS certificates automatically."
        echo "Please install openssl or place tls.crt and tls.key under dfxw/nginx-ssl/."
        exit 1
    fi

    echo "Generating self-signed UI TLS certificate under dfxw/nginx-ssl ..."
    openssl req -x509 -nodes -days 3650 \
        -newkey rsa:2048 \
        -keyout "$tls_key" \
        -out "$tls_crt" \
        -subj "/C=CN/ST=Beijing/L=Beijing/O=EAP/OU=DFXW/CN=localhost"
}

if [[ "$ACTION" == "stop" ]]; then
    echo "Stopping all EKBA services..."
    # stop app services
    (cd dfxw && $_DC_CMD down)

    # Try to stop both OVMS and TEI services since we don't know which one was running
    (cd dfxw/tei-models-serving && $_DC_CMD down)

    # stop backend services
    (cd backends/eap-common && $_DC_CMD down)

    echo "All services have been stopped"
    exit 0
fi

echo "Launch EKBA application and services step by step:"

ensure_ui_tls_files

SHOULD_PULL_REMOTE_IMAGES=0
if asking "Do you want to pull and retag images from remote registry first?"; then
    SHOULD_PULL_REMOTE_IMAGES=1
else
    echo "Using local images directly."
fi

echo "Checking .env in dfxw directory..."

(
    cd dfxw

    if [ -f ".env" ]; then
        if asking "Detected dfxw/.env, do you want to use it directly?"; then
            echo "Using existing .env to launch EKBA application."
        else
            echo "Regenerating dfxw/.env..."
            ./set-env.sh

            if asking "Do you want to double check .env file?" "N"; then
                ${EDITOR:-vi} .env
            fi
        fi
    else
        echo "No .env found. Running env configuration workflow..."
        ./set-env.sh

        if asking "Do you want to double check .env file?" "N"; then
            ${EDITOR:-vi} .env
        fi
    fi
)

DFXW_REGISTRY=$(read_env_value "dfxw/.env" "REGISTRY" "localhost:5000")
DFXW_TAG=$(read_env_value "dfxw/.env" "TAG" "latest")

if [ "$SHOULD_PULL_REMOTE_IMAGES" -eq 1 ]; then
    prepare_images "$DFXW_REGISTRY" "$DFXW_TAG"
else
    echo "Skipping remote pull and tag step."
    echo "Expecting local business images like ${DFXW_REGISTRY}/ekba/*:${DFXW_TAG}"
    echo "Expecting local backend images like mongo:7.0.11"
fi

if asking "Do you want to launch ALL backend services in one step?"; then
    echo "Launching all backend services..."
    (cd backends/eap-common && $_DC_CMD up -d)
else

    # Check and lanuch backend services one by one

    ## Minio
    if asking "Launch Minio?"; then
        echo "Launching Minio..."
        (cd backends/eap-common && $_DC_CMD up minio -d)
    fi

    ## Milvus
    if asking "Launch Milvus?"; then
        echo "Launching Milvus..."
        (cd backends/eap-common && $_DC_CMD up milvus-standalone -d)
    fi

    ## Mongo DB
    if asking "Launch Mongo DB?"; then
        echo "Launching Mongo DB..."
        (cd backends/eap-common && $_DC_CMD up mongodb -d)
    fi

    ## Redis
    if asking "Launch Redis?"; then
        echo "Launching Redis..."
        (cd backends/eap-common && $_DC_CMD up redis -d)
    fi

    ## MySQL
    if asking "Launch MySQL?"; then
        echo "Launching MySQL..."
        (cd backends/eap-common && $_DC_CMD up mysql -d)
    fi
fi

## Finally launch the EKBA application
echo "Launching EKBA application..."
(cd dfxw && $_DC_CMD up -d)

UI_PORT=$(grep -E "^EKBA_UI_PORT=" dfxw/.env 2>/dev/null | tail -n1 | cut -d'=' -f2)
UI_PORT=${UI_PORT:-5174}
echo "All EKBA services have been launched, please check the UI at: https://localhost:${UI_PORT} "

echo "All done, congratulations!"

# clean up
unset _DC_CMD
