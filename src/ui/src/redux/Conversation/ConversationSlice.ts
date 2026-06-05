// Copyright (C) 2024 Intel Corporation
// SPDX-License-Identifier: Apache-2.0

import { PayloadAction, createSlice } from "@reduxjs/toolkit";
import { RootState, store } from "../store";
import { fetchEventSource } from "@microsoft/fetch-event-source";
import { Message,
         MessageRole,
         ConversationReducer,
         ConversationRequest,
         Conversation,
         TracedFileInfo,
         ToolInfo,
         isValidKBSList,
         isValidKBFilesList,
         isValidKBQuestionList} from "./Conversation";
import { getCurrentTimeStamp, uuidv4 } from "../../common/util";
import { createAsyncThunkWrapper } from "../thunkUtil";
import client from "../../common/client";
import { notifications } from "@mantine/notifications";
import {
  URL_RAG_BACKEND,
  URL_LLM_CHAT,
  URL_KBS_LIST,
  URL_KBS_GET_FILES,
  URL_KBS_GET_QUESTIONS,
  URL_CHAT_HISTORY_CREATE,
  URL_CHAT_HISTORY_GET,
  URL_CHAT_HISTORY_DELETE,
  URL_CHAT_FEEDBACK_UPDATE,
  COLLECTION_NAME,
    URL_MCP_LIST,
    NEW_IP
} from "../../config";
import type {
  IHighlight,
  Scaled,
} from "react-pdf-highlighter";

// ragflow kb no longer use this, keep it for backward compatibility
// Change it to 1.0 for ragflow kb
const scaleRatio = 1;
const initialState: ConversationReducer = {
  conversations: [],
  selectedConversationId: "",
  selectedConversationHistory: [],
  onGoingResult: "",
  onGoingDocMeta: "",
  filesInDataSource: [],
  filesTraced: [],
  promptOption: false, // false means keep history, true means prompt only
  collections: {},
  mcpList:[],
  selectedCollection: COLLECTION_NAME,
  selectedDynamicOption: "",
  collectionQuestionList: [],
  isStreaming: false,
  currentSessionId: "" // 新增：存储全局Session ID
};

export const ConversationSlice = createSlice({
  name: "Conversation",
  initialState,
  reducers: {
    logout: (state) => {
      state.conversations = [];
      state.selectedConversationId = "";
      state.onGoingResult = "";
      state.selectedConversationHistory = [];
      state.onGoingDocMeta = "";
      state.filesInDataSource = [];
      state.filesTraced=[];
      state.promptOption = false;
      state.selectedCollection = "";
      state.isStreaming = false;
    },
    setCurrentSessionId: (state, action: PayloadAction<string>) => {
      state.currentSessionId = action.payload;
    },
    setOnGoingResult: (state, action: PayloadAction<string>) => {
      state.onGoingResult = action.payload;
    },
    setOnGoingDocMeta: (state, action: PayloadAction<string>) => {
      state.onGoingDocMeta = action.payload;
    },
    addMessageToMessages: (state, action: PayloadAction<Message>) => {
      state.selectedConversationHistory.push(action.payload);
    },
    updateLastMessageFeedbackAndReferences: (state, action: PayloadAction<{ feedback: string; references: TracedFileInfo[] }>) => {
      const { feedback, references } = action.payload;
      const lastIndex = state.selectedConversationHistory.length - 1;
      if (lastIndex >= 0) {
        state.selectedConversationHistory[lastIndex].feedback = feedback;
        state.selectedConversationHistory[lastIndex].current_references = references;
      }
    },
    newConversation: (state) => {
      (state.selectedConversationId = ""), (state.onGoingResult = ""), (state.selectedConversationHistory = []), (state.promptOption = false);
    },
    setSelectedConversationId: (state, action: PayloadAction<string>) => {
      state.selectedConversationId = action.payload;
    },
    clearTracedFiles: (state) => {
      state.filesTraced = []
    },
    setTraceFiles: (state, action: PayloadAction<TracedFileInfo[] | undefined>) => {
      if (action.payload !== undefined){
        state.filesTraced = action.payload;
      }
    },
    storeTracedFiles: (state, action: PayloadAction<{ fileName?: string;filePath: string; reference:IHighlight[]; sourceUrl?: string; publishTime?: string; title?: string ; type?: string; mcp?: ToolInfo[],rowId?:string; position?:string; trainType?:string;link?: string}>) => {
      // Find if there's already TracedFileInfo object that obtains the same file name
      // If so, merge the info
      const existingIndex = state.filesTraced.findIndex(item => item.fileName === action.payload.fileName);
      if (existingIndex !== -1) {
        const existingObject = state.filesTraced[existingIndex];
        const mergedRef = Array.from(new Set([...existingObject.reference, ...action.payload.reference])); // Remove duplicates

        // Replace the existing object with the new merged object
        state.filesTraced[existingIndex] = { ...existingObject, reference: mergedRef };
      } else {
        state.filesTraced.push({
          fileName: action.payload.fileName,
          filePath: action.payload.filePath,
          reference: action.payload.reference,
          sourceUrl: action.payload.sourceUrl,
          publishTime: action.payload.publishTime,
          title: action.payload.title,
          type: action.payload.type,
          link: action.payload.link,
          mcp: action.payload.mcp,
          trainType: action.payload.trainType,
          rowId: action.payload.rowId,
          position: action.payload.position,
        })
      }
    },
    setPromptOption: (state, action: PayloadAction<boolean | undefined>) => {
      if (action.payload !== undefined) {
        state.promptOption = action.payload;
      }
    },
    setSelectedCollection: (state, action: PayloadAction<string | undefined>) => {
      if (action.payload !== undefined) {
        if(action.payload !== "" && action.payload !== "SKIP" && state.mcpList !== undefined){
          state.mcpList.forEach(item => {
            if (item.flag !== 'RAG') {
              item.enabled = false;
            }
          });
        }
        state.selectedCollection = action.payload;
      } else {
        state.selectedCollection = ""
      }
    },

    setSelectedDynamicOption: (state, action: PayloadAction<string | null>) => {
      state.selectedDynamicOption = action.payload;
    },
    
    // setWebSearch: (state, action: PayloadAction<boolean | undefined>) => {
    //   if (action.payload !== undefined) {
    //     state.isWebSearch = action.payload;
    //   } else {
    //     state.isWebSearch = false
    //   }
    // },
    setMcpList: (state, action: PayloadAction<string | undefined>) => {
      if (action.payload !== undefined) {
        const foundItem = state.mcpList.find((item) => item.tool_path === action.payload);
        if (foundItem) {
          foundItem.enabled = !foundItem.enabled;
        }

      }
    },
    deleteLocalConversation: (state, action: PayloadAction<string>) => {
      const existingIndex = state.conversations.findIndex(x=>x.id===action.payload);
      if (existingIndex !== -1) {
        state.conversations.splice(existingIndex, 1);
      }
    },
    setIsStreaming: (state, action: PayloadAction<boolean>) => {
      state.isStreaming = action.payload;
    },
  },
  extraReducers(builder) {
    builder.addCase(getAllConversations.fulfilled, (state, action) => {
      state.conversations = action.payload;
    });
    builder.addCase(getConversationHistory.fulfilled, (state, action) => {
      state.selectedConversationHistory = action.payload.messages;
      state.filesTraced = action.payload.last_query_trace_data;
      state.promptOption = action.payload.current_prompt_only;
    });
    builder.addCase(updateFeedback.fulfilled, (state, action) => {
      let index = action.payload.update_message_index;
      let feedback = action.payload.feedback;
      state.selectedConversationHistory[index].feedback = feedback;
    });
    builder.addCase(saveConversationtoDatabase.fulfilled, (state, action) => {
      if (state.selectedConversationId == "") {
        state.selectedConversationId = action.payload;
        state.conversations.push({
          id: action.payload,
          first_query: state.selectedConversationHistory[0].content,
          last_query_trace_data: state.filesTraced,
          current_prompt_only: state.promptOption,
        });
      } else {
        const existingIndex = state.conversations.findIndex(x=>x.id===state.selectedConversationId);
        if (existingIndex !== -1) {
          const updatedConversation = {
            id: state.selectedConversationId,
            last_query_trace_data: state.filesTraced,
            current_prompt_only: state.promptOption,
          };
          state.conversations[existingIndex] = { ...state.conversations[existingIndex], ...updatedConversation};
        };
      }
    });
    builder.addCase(getAllFilesInDataSource.fulfilled, (state, action) => {
      state.filesInDataSource = action.payload.map(file => ({ name: file.name }));
    });
    builder.addCase(deleteConversation.fulfilled, () => {
      notifications.show({
        message: "Conversation Deleted Successfully",
      });
    });
    builder.addCase(getCollections.fulfilled, (state, action) => {
      state.collections = action.payload;
    });
    builder.addCase(getMcpList.fulfilled, (state, action) => {
      state.mcpList = action.payload;
    });
    builder.addCase(getCollectionQuestionList.fulfilled, (state, action) => {
      state.collectionQuestionList = action.payload;
    });
  },
});


export const getAllFilesInDataSource = createAsyncThunkWrapper(
  "conversation/getAllFilesInDataSource",
  async ({ collectionName, knowledgeBaseId = "default" }: { collectionName: string, knowledgeBaseId?: string }) => {
    // TODO: use kb_id later, currently use collectionName as a workaround
    // Replace the placeholder {kb_id} in the URL with the actual collection name

    console.log("get file list for collectionName(kb_id)", collectionName, knowledgeBaseId);

    if (collectionName === "" || collectionName === "SKIP") {

      if (collectionName === "SKIP") {
        // trigger action to refresh the KB list
        console.log('to refresh the KB list...');
        const response = await fetch(URL_KBS_LIST, {
          method: 'POST',
        });
        if (!response.ok) {
          console.log('refresh the KB list failed');
        } else {
          // call getCollections to refresh the KB list
          store.dispatch(getCollections(undefined));
        }
      }

      return []
    }

    let collections = store.getState().conversationReducer.collections;
    let kb_id = collections[collectionName];

    console.log("collectionName and ID", collectionName, kb_id);

    const url = URL_KBS_GET_FILES.replace('{kb_id}', kb_id);
    const response = await client.get(url);

    let data = response.data;
    try {
      if (!isValidKBFilesList(data)) {
        throw new Error("Invalid JSON response of KB files list");
      }
    } catch (error) {
      console.log("Invalid JSON response of KB files list");
      return [];
    }

    return data;
  },
);

export const saveConversationtoDatabase = createAsyncThunkWrapper(
  "conversation/saveConversationtoDatabase",
  async ({ conversation }: { conversation: Conversation }, { getState }) => {
    // @ts-ignore
    const state: RootState = getState();
    // const selectedConversationHistory = state.conversationReducer.selectedConversationHistory;
    const traceData = state.conversationReducer.filesTraced;
    
    let traceDataList = []
    for (let data of traceData) {
      let serializedData = JSON.parse(JSON.stringify(data));
      traceDataList.push(serializedData);
    }
    // user's feedback is null and set to empty string
    store.dispatch(updateLastMessageFeedbackAndReferences({ feedback: "", references: traceDataList }));
    // update root state
    const updatedState: RootState = getState() as RootState;

    const selectedConversationHistory = updatedState.conversationReducer.selectedConversationHistory;
    
    const response = await client.post(URL_CHAT_HISTORY_CREATE, {
      data: {
        user: state.userReducer.name,
        messages: selectedConversationHistory,
        current_prompt_only: state.conversationReducer.promptOption,
        last_query_trace_data: traceDataList,
      },
      id: conversation.id == "" ? null : conversation.id,
      first_query: selectedConversationHistory[0].content,
    });
    
    return response.data;
  },
);

export const getAllConversations = createAsyncThunkWrapper(
  "conversation/getAllConversations",
  async ({ user }: { user: string }, {}) => {
    const response = await client.post(URL_CHAT_HISTORY_GET, {
      user,
    });
    return response.data;
  },
);

export const getConversationHistory = createAsyncThunkWrapper(
  "conversation/getConversationHistory",
  async ({ user, conversationId }: { user: string; conversationId: string }, {}) => {
    const response = await client.post(URL_CHAT_HISTORY_GET, {
      user,
      id: conversationId,
    });
    return response.data;
  },
);

export const deleteConversation = createAsyncThunkWrapper(
  "conversation/delete",
  async ({ user, conversationId }: { user: string; conversationId: string }, { dispatch }) => {
    const response = await client.post(URL_CHAT_HISTORY_DELETE, {
      user,
      id: conversationId,
    });

    dispatch(newConversation());
    // Disable get conversation history for 'Anonymous' user
    if ( user !== "Anonymous") {
      dispatch(getAllConversations({ user }));
    }
    return response.data;
  },
);

export const getCollections = createAsyncThunkWrapper(
  "conversation/getCollections",
  async () => {
    const response = await client.get(URL_KBS_LIST);
    let data = response.data;

    // Validate that the response data is valid JSON
    try {
      if (!isValidKBSList(data)) {
        throw new Error("Invalid JSON response of KB list");
      }
    } catch (error) {
      console.log("Invalid JSON response of KB list");
      return {};
    }
    for (let collection of Object.entries(data)) {
      if (collection[1] === "") {
        // let kb_id be the same as collection name for old format KBs
        data[collection[0]] = collection[0];
      } else {
        data[collection[0]] = "kb_" + collection[1];
      }
    }
    return data;
  },
);

export const getMcpList = createAsyncThunkWrapper(
  "conversation/getMcpList",
  async () => {
    const response = await client.post(URL_MCP_LIST);
    return response.data;
  },
);

export const getCollectionQuestionList = createAsyncThunkWrapper(
  "conversation/getCollectionQuestionList",
  async (selectedCollection: string) => {
    if (selectedCollection === "SKIP") {
      return []
    }
    let collections = store.getState().conversationReducer.collections;
    let kb_id =  collections[selectedCollection];

    const url = URL_KBS_GET_QUESTIONS.replace('{kb_id}', kb_id);
    const response = await client.get(url);
    let data = response.data;
    try {
      if (!isValidKBQuestionList(data)) {
        throw new Error("Invalid JSON response of KB question list");
      }
    } catch (error) {
      console.log("Invalid JSON response of KB question list");
      return [];
    }
    return data;
  },
);

export const updateFeedback = createAsyncThunkWrapper(
  "conversation/update_feedback",
  async ({type, index, name, selectedConversationId}:
    {type: string, index: number, name: string, selectedConversationId: string}, {}
  ) => {
    await client.post(URL_CHAT_FEEDBACK_UPDATE,{
      id: selectedConversationId,
      user: name,
      feedback: type,
      update_message_index: index,
    });
    return { feedback: type, update_message_index: index };
  },
);

export const doConversation = (conversationRequest: ConversationRequest) => {
  const { conversationId, userPrompt, messages, historyOption, collectionName,dynamicOption, signal,mcpList } = conversationRequest;
  store.dispatch(addMessageToMessages(userPrompt));
  const isRAGChat = collectionName !== "SKIP";
  let apiUrl = null
  const pathList = mcpList
  .filter(item => item.enabled === true)
  .map(item => item.tool_path);
  // if(isWebSearch){
  //   apiUrl = CHAT_QNA_URL
  // }else{
  apiUrl = isRAGChat || pathList.length > 0 ? URL_RAG_BACKEND: URL_LLM_CHAT
  // }

  let body: any;

  const userPromptWithoutTime = {
    role: userPrompt.role,
    content: userPrompt.content,
  };



  let result = "";
  let docMeta = "";
  let mcpMeta = "";
  let tokenMeta = "";
  let dataEnd = false;

  signal?.addEventListener('abort', () => {
    console.log("Request aborted manually");
    executeCloseLogic(
      result,
      docMeta,
      mcpMeta,
      tokenMeta,
      conversationId,
      historyOption
    );
  });
  
  if (dynamicOption != "" && dynamicOption != undefined){
    if (conversationId === "") {
      // 1. 生成新的Session ID
      const session_id_conv = uuidv4();
      // 2. 存入Redux（全局可访问）
      store.dispatch(setCurrentSessionId(session_id_conv));
    }
    apiUrl = NEW_IP,
      body = {
      messages: [...messages, userPromptWithoutTime],
      session_id: store.getState().conversationReducer.currentSessionId,
      source_file_name: dynamicOption
    };
  }else{
    if (apiUrl === URL_LLM_CHAT) {
      //Construct URL_LLM_CHAT request body
      body = {
        messages: [...messages, userPromptWithoutTime],
        top_p: 0.95,
        temperature: 0.01,
        stream: true,
        stream_options: {"include_usage": true}
      };
    } else {
      //Construct URL_CHAT_BACKEND request body
      body = {
        messages: [...messages, userPromptWithoutTime],
        collection_name: collectionName,
        score_threshold: 0.2,
        mcp_list: pathList,
        stream: true,
        stream_options: {"include_usage": true},
      };
    }
  }

  try {
    fetchEventSource(apiUrl, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(body),
      openWhenHidden: true,
      signal: signal,
      async onopen(response) {
        if (response.ok) {
          return;
        } else if (response.status >= 400 && response.status < 500 && response.status !== 429) {
          const e = await response.json();
          console.log(e);
          throw Error(e.error.message);
        } else {
          console.log("error", response);
        }
      },
      
      onmessage(msg) {
        if (msg?.data !== "[METADATA DONE]") {
          if (msg?.data == "[DONE]") {
            dataEnd = true;
          }
          try {
            // Match either b'...' or b"..."
              const match = msg.data.match(/b(['"])((?:(?!\1).)*)\1/);
              if (/^b['"]/.test(msg.data) && match && match[2] != "</s>") {
                let extractedText = match[2];

                // 替换-为换行
                extractedText = extractedText;

              // Check for the presence of \x hexadecimal
              if (extractedText.includes("\\x")) {
                // Decode Chinese (or other non-ASCII characters)
                const decodedText = decodeEscapedBytes(extractedText);
                result += decodedText;
              } else {
                result += extractedText;
              }
            }  else if (!/^b['"]/.test(msg.data) && msg?.data.includes("tool_info")) {

                mcpMeta += msg?.data;
              }
            else if (!/^b['"]/.test(msg.data)) {
              // Return data without pattern
              if (dataEnd && msg?.data?.includes("token_usage")) {
                tokenMeta += msg?.data;
              } else if (dataEnd && msg?.data.includes("documents")) {
                docMeta += msg?.data;
              } else if (msg?.data != "[DONE]") {
                // 替换-为换行
                result += msg?.data;
              }
            }
            // Store back result if it is not null
            if (result) {
              store.dispatch(setOnGoingResult(result));
            }
            // Store back document metadata if exists
            if (docMeta) {
              store.dispatch(setOnGoingDocMeta(docMeta));
            }
          } catch (e) {
            console.log("something wrong in msg", e);
            throw e;
          }
        }
      },
      onerror(err) {
        console.log("error", err);
        store.dispatch(setOnGoingResult(""));
        store.dispatch(setOnGoingDocMeta(""));
        //notify here
        throw err;
        //handle error
      },
      onclose() {
        executeCloseLogic(
          result,
          docMeta,
          mcpMeta,
          tokenMeta,
          conversationId,
          historyOption
        )
      },
    });
  } catch (err) {
    console.log(err);
  }
};


const executeCloseLogic = (
  result: string,
  docMeta: string,
  mcpMeta: string,
  tokenMeta: string,
  conversationId: string,
  historyOption: any,
) => {
  //handle close
  store.dispatch(setOnGoingResult(""));
  store.dispatch(setOnGoingDocMeta(""));
  store.dispatch(setPromptOption(historyOption));

  let message :Message= {
    role: MessageRole.Assistant,
    content: result,
    time: getCurrentTimeStamp().toString(),
  }

  if (tokenMeta !== "") {
    try {
      let tmp_usage = JSON.parse(tokenMeta);
      message.token_usage = {
        prompt_tokens: tmp_usage.token_usage.prompt_tokens,
        completion_tokens: tmp_usage.token_usage.completion_tokens,
        total_tokens: tmp_usage.token_usage.total_tokens,
      };
    } catch (e) {
      console.warn("Failed to parse tmp_usage JSON:", e);
      throw e;
    }
  }
  store.dispatch(
    addMessageToMessages(message),
  );

        // Provide a new list to contain trace files
        store.dispatch(clearTracedFiles());
        let sanitizedMeta = docMeta.replace(/[\n\r\t]/g, '\\n');
        let mcp = mcpMeta.replace(/[\n\r\t]/g, '\\n');
        let jsonDocMeta: any;
        let jsonMcp: any;
        try {
          if (sanitizedMeta) {
            jsonDocMeta = JSON.parse(sanitizedMeta);
          }
          if (mcp) {
            jsonMcp = JSON.parse(mcp);
          }
        } catch (error) {
          console.error("Failed to parse JSON:", error);
        }
        // console.log("jsonDocMeta", jsonDocMeta);
        if (!jsonDocMeta){
          let refArray: Array<IHighlight> = []
          let mcp = jsonMcp?.tool_info;
          let decodedName;
          let sourceUrl;
          let publishTime;
          let title;
          let type;
          let link;
          // let position;
          // let rowId;
          // let trainType;
          store.dispatch(
            storeTracedFiles({
              fileName: decodedName,
              filePath: "",
              reference: refArray,
              sourceUrl: sourceUrl,
              publishTime: publishTime,
              title: title,
              type: type,
              link: link,
              mcp: mcp,
            })
          );
        }else{
          for (let i = 0; i < jsonDocMeta?.documents.length; i++) {
            const doc = jsonDocMeta?.documents[i];
            // construct a list of highlights
            let refArray: Array<IHighlight> = []
            // decode the filename string in case it is URL encoded
            let decodedName;
            let sourceUrl;
            let publishTime;
            let title;
            let type;
            let link;
            let mcp = jsonMcp?.tool_info;
            let position = decodeURIComponent(doc?.metadata?.position);
            let rowId = decodeURIComponent(doc?.metadata?.rowId);
            let trainType = decodeURIComponent(doc?.metadata?.trainType);

            decodedName = decodeURIComponent(doc?.metadata?.filename)
            type = decodeURIComponent(doc?.metadata?.type)
            // extract rect, page size from the metadata that shall locate in the same file and page
            // and push into the refArray list as single Ihighlight object
            let x1 = parseInt(doc?.metadata?.rect?.x1, 10)*scaleRatio;
            let y1 = parseInt(doc?.metadata?.rect?.y1, 10)*scaleRatio;
            let x2 = parseInt(doc?.metadata?.rect?.x2, 10)*scaleRatio;
            let y2 = parseInt(doc?.metadata?.rect?.y2, 10)*scaleRatio;
            let width = parseInt(doc?.metadata?.page?.width, 10)*scaleRatio;
            let height = parseInt(doc?.metadata?.page?.height, 10)*scaleRatio;
            let rectItem: Scaled = {
              "x1": x1,
              "y1": y1,
              "x2": x2,
              "y2": y2,
              "width": width,
              "height": height,
              "pageNumber": doc?.metadata?.page?.page_num,
            }
            // create a random id for an Ihighlight object
            let id = Math.floor(Math.random() * 10000000) + 1

            refArray.push({
              "content": {
                "text": doc?.text,
              },
              "position": {
                "boundingRect": rectItem,
                "rects": [rectItem],
                "pageNumber":doc?.metadata?.page?.page_num,
              },
              "comment":{
                "text": "",
                "emoji": "",
              },
              "id": id.toString(),
            })
            // store and clean the reference data
            store.dispatch(
              storeTracedFiles({
                fileName: decodedName,
                filePath: doc?.metadata?.filepath,
                reference: refArray,
                sourceUrl: sourceUrl,
                publishTime: publishTime,
                title: title,
                type: type,
                link: link,
                mcp: mcp,
                position: position,
                rowId: rowId,
                trainType: trainType,
              })
            );
          }
        }

  // store the conversation history and properties back to db
  store.dispatch(
    saveConversationtoDatabase({
      conversation: {
        id: conversationId,
      },
    }),
  );
  store.dispatch(setIsStreaming(false));
}

export const {
  logout,
  setOnGoingResult,
  setOnGoingDocMeta,
  newConversation,
  addMessageToMessages,
  updateLastMessageFeedbackAndReferences,
  setSelectedConversationId,
  clearTracedFiles,
  setTraceFiles,
  storeTracedFiles,
  setPromptOption,
  setSelectedCollection,
  setSelectedDynamicOption,
  setMcpList,
  deleteLocalConversation,
  setIsStreaming,
  setCurrentSessionId, // 新增导出
} = ConversationSlice.actions;
export const conversationSelector = (state: RootState) => state.conversationReducer;
export default ConversationSlice.reducer;

// decode \x hexadecimal encoding
function decodeEscapedBytes(str: string): string {
  let byteArray: number[] = [];
  let i = 0;

  while (i < str.length) {
      if (str[i] === '\\' && i + 1 < str.length) {
          const nextChar = str[i + 1];

          if (nextChar === 'x') {
              // Handle \xNN hex escape sequences
              const hex = str.substring(i + 2, i + 4);
              const byte = parseInt(hex, 16);
              byteArray.push(byte);
              i += 4; // Move past \xNN
          } else if (nextChar === 'n') {
              // Handle \n (newline)
              byteArray.push(10); // ASCII code for newline '\n'
              i += 2; // Move past \n
          } else {
              // For other escape sequences, add the character as is
              byteArray.push(str.charCodeAt(i + 1));
              i += 2;
          }
      } else {
          // Regular character
          byteArray.push(str.charCodeAt(i));
          i++;
      }
  }

  // Decode the byte array into a UTF-8 string
  const decodedString = new TextDecoder("utf-8").decode(new Uint8Array(byteArray));

  return decodedString;
}
