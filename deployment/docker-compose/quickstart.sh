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

if [[ "$ACTION" == "stop" ]]; then
    echo "Stopping all EKBA services..."
    # stop app services
    (cd ekba && $_DC_CMD down)

    # Try to stop both OVMS and TEI services since we don't know which one was running
    (cd backends/ovms-models-serving && $_DC_CMD down)
    (cd backends/tei-models-serving && $_DC_CMD down)

    # stop backend services
    (cd backends/eap-common && $_DC_CMD down)

    echo "All services have been stopped"
    exit 0
fi

echo "Launch EKBA application and services step by step:"

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

## OVMS or TEI model serving
if asking "Do you want to launch OVMS or TEI model serving?"; then
    choose_one "Which one do you want to launch?" "OVMS" "TEI"
    echo "Launching $_model_serving model serving(embedding and reranker)..."
    echo "WARN: REGISTRY should be set in .env file(copy from env.example and modify)"
    (cd backends/${_model_serving,,}-models-serving && $_DC_CMD up -d)
fi

## Config the endpoints and envs
echo "Before launching the EKBA application, please config the endpoints and envs"
(
    cd ekba
    ./set-env.sh
    if asking "Do you want to double check .env file?" "N"; then
        ${EDITOR:-vi} .env
    fi
)

## Finally launch the EKBA application
echo "Launching EKBA application..."
(cd ekba && $_DC_CMD up -d)

echo "All EKBA services have been launched, please check the UI at: http://localhost:5174 "

echo "All done, congratulations!"

# clean up
unset _DC_CMD
