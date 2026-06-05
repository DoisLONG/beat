// Copyright (C) 2024 Intel Corporation
// SPDX-License-Identifier: Apache-2.0

import { combineReducers, configureStore } from "@reduxjs/toolkit";
import userReducer from "./User/userSlice";
import conversationReducer from "./Conversation/ConversationSlice";
import { TypedUseSelectorHook, useDispatch, useSelector } from "react-redux";

export const store = configureStore({
  reducer: combineReducers({
    userReducer,
    conversationReducer,
  }),
  // devTools: import.meta.env.PROD || true,
  preloadedState: loadFromLocalStorage(),
  middleware: (getDefaultMiddleware) =>
    getDefaultMiddleware({
      serializableCheck: false,
    }),
});

function saveToLocalStorage(state: ReturnType<typeof store.getState>) {
  try {
    const stateToSave = {
      state,
      timestamp: Date.now(), // Add a timestamp
    };
    const serialState = JSON.stringify(stateToSave);
    localStorage.setItem("reduxStore", serialState);
  } catch (e) {
    console.warn(e);
  }
}

function loadFromLocalStorage() {
  try {
    const serialisedState = localStorage.getItem("reduxStore");
    if (serialisedState === null) return undefined;
    const parsedState = JSON.parse(serialisedState);
    const savedTime = parsedState.timestamp; // Assume timestamp is stored in the state
    const currentTime = Date.now();

    // Check if the cached data is older than 1 hour (3600000 ms)
    if (currentTime - savedTime > 3600000) {
      return undefined; // Clear the state if it's too old
    }

    return parsedState.state;
  } catch (e) {
    console.warn(e);
    return undefined;
  }
}

export function clearConversationHistory(conversationId: string) {
  try {
    console.log("clearConversationHistory", conversationId);
    const serialisedState = localStorage.getItem("reduxStore");
    if (serialisedState === null) return undefined;
    const parsedState = JSON.parse(serialisedState);
    const state = parsedState.state;
    // just clean up some fields and reserve questionList
    state.conversationReducer.conversations = [];
    state.conversationReducer.selectedConversationId = "";
    state.conversationReducer.selectedConversationHistory = [];
    state.conversationReducer.collectionQuestionList = [];
    state.conversationReducer.filesTraced = [];
    const stateToSave = {
      state,
      timestamp: Date.now(), // Add a timestamp
    };
    const serialState = JSON.stringify(stateToSave);
    localStorage.setItem("reduxStore", JSON.stringify(serialState));
  } catch (e) {
    console.warn(e);
  }
}

store.subscribe(() => saveToLocalStorage(store.getState()));
export default store;
export type AppDispatch = typeof store.dispatch;
export type RootState = ReturnType<typeof store.getState>;

export const useAppDispatch: () => AppDispatch = useDispatch;
export const useAppSelector: TypedUseSelectorHook<RootState> = useSelector;
