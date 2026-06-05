// Copyright (C) 2024 Intel Corporation
// SPDX-License-Identifier: Apache-2.0

export const getCurrentTimeStamp = () => {
  return Math.floor(Date.now() / 1000);
};

// 全局聊天状态管理（解决newChatInitialId页面刷新重置问题）
export const globalChatState = {
  newChatInitialId: "" as string,
  // 可扩展其他需要跨组件/跨页面共享的聊天状态
};


export const uuidv4 = () => {
  return "10000000-1000-4000-8000-100000000000".replace(/[018]/g, (c) =>
    (+c ^ (crypto.getRandomValues(new Uint8Array(1))[0] & (15 >> (+c / 4)))).toString(16),
  );
};
