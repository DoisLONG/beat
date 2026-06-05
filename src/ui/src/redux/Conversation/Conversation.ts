// Copyright (C) 2024 Intel Corporation
// SPDX-License-Identifier: Apache-2.0

import type {
  IHighlight
} from "react-pdf-highlighter";

export type ConversationRequest = {
  conversationId: string;
  userPrompt: Message;
  messages: Message[];
  model?: string;
  // need modification
  historyOption?: boolean;
  collectionName: string;
  dynamicOption: string | null,
  // isWebSearch: boolean;
  mcpList:McpInfo[];
  signal?: AbortSignal;
};
export enum MessageRole {
  Assistant = "assistant",
  User = "user",
  System = "system",
}

export interface Message {
  role: MessageRole;
  content: string;
  time?: string;
  feedback?: string;
  token_usage?: TokenUsage;
  current_references?: TracedFileInfo[];
}

export interface TokenUsage {
  prompt_tokens: number;
  completion_tokens: number;
  total_tokens: number;
}

export interface Conversation {
  id: string;
  first_query?: string;
  current_prompt_only?: boolean;
  last_query_trace_data?: TracedFileInfo[];
}

export interface TracedFileInfo {
  fileName?: string;
  filePath: string;
  reference: IHighlight[];
  sourceUrl?: string;
  publishTime?: string;
  title?: string;
  type?:string;
  link?:string;
  mcp?:ToolInfo[];
  rowId?:string;
  position?:string;
  trainType?:string;
}

export interface ToolInfo {
  name?: string;
  result?:string;
}

export interface McpInfo {
  tool_name?: string;
  tool_path?: string;
  flag?: string;
  enabled?: boolean;
}

export interface FileInfo {
  name: string;
};

export interface ConversationReducer {
  conversations: Conversation[];
  selectedConversationId: string;
  selectedConversationHistory: Message[];
  onGoingResult: string;
  onGoingDocMeta: string;
  filesInDataSource: FileInfo[];
  filesTraced: TracedFileInfo[];
  promptOption: boolean;
  collections: {[key: string]: string};
  mcpList:McpInfo[];
  selectedCollection: string;
  selectedDynamicOption: string | null;
  collectionQuestionList: string[];
  isStreaming: boolean;
  currentSessionId: string;
}

type KBSList = { [key: string]: string };
export function isValidKBSList(data: any): data is KBSList {
  return typeof data === "object" &&
                data !== null &&
                Object.keys(data).every(key => typeof key === "string") &&
                Object.values(data).every(value => typeof value === "string");
}

type KBFilesList = Array<{ [key: string]: string }>;
export function isValidKBFilesList(list: any): list is KBFilesList {
  return Array.isArray(list) && list.every(item => typeof item === "object" && item !== null && typeof item.name === "string");
}

type KBQuestionList = Array<string>;
export function isValidKBQuestionList(list: any): list is KBQuestionList {
  return Array.isArray(list) && list.every(item => typeof item === "string");
}