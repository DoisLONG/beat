// Copyright (C) 2024 Intel Corporation
// SPDX-License-Identifier: Apache-2.0

export const URL_RAG_BACKEND = "/v1/chatqna";
export const URL_LLM_CHAT = "/v1/chat/completions";
export const URL_MCP_LIST = "/v1/mcp/infos";

export const URL_KBS_LIST = "/v1/kbs";
export const URL_KBS_GET_INFO = "/v1/kbs/{kb_id}"; // not used so far
export const URL_KBS_GET_FILES = "/v1/kbs/files/{kb_id}";
export const URL_KBS_GET_QUESTIONS = "/v1/kbs/questions/{kb_id}";

export const URL_CHAT_HISTORY_CREATE = "/v1/chathistory/create";
export const URL_CHAT_HISTORY_GET    = "/v1/chathistory/get";
export const URL_CHAT_HISTORY_DELETE = "/v1/chathistory/delete";
export const URL_CHAT_FEEDBACK_UPDATE = "/v1/chathistory/feedback/update";

export const URL_FILE_DOWNLOAD = "/ekbafiles-";
export const URL_EXCELS = "/v1/dataprep/sops";

export const NEW_IP = "/v1/train/chat";

export const COLLECTION_NAME = import.meta.env.VITE_DEFAULT_KB;