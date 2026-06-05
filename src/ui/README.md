# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

# ChatQnA Conversational UI

## 📸 Project Screenshots

![project-screenshot](../../../assets/img/conversation_ui_init.png)
![project-screenshot](../../../assets/img/conversation_ui_response.png)
![project-screenshot](../../../assets/img/conversation_ui_upload.png)

## 🧐 Features

Here're some of the project's features:

- Start a Text Chat：Initiate a text chat with the ability to input written conversations, where the dialogue content can also be customized based on uploaded files.
- Context Awareness: The AI assistant maintains the context of the conversation, understanding references to previous statements or questions. This allows for more natural and coherent exchanges.
- Upload File: The choice between uploading locally or copying a remote link. Chat according to uploaded knowledge base.
- Clear: Clear the record of the current dialog box without retaining the contents of the dialog box.
- Chat history: Historical chat records can still be retained after refreshing, making it easier for users to view the context.
- Conversational Chat : The application maintains a history of the conversation, allowing users to review previous messages and the AI to refer back to earlier points in the dialogue when necessary.

## ️🚀 Get it Running

1. Clone the repo.

2. cd command to the current folder.

3. copy env.example to .env at first.

4. Modify the required .env variables.
   ```
   DOC_BASE_URL = ''
   ```
5. Execute `npm install` to install the corresponding dependencies.

6. Execute `npm run dev` in both environments

## 🛠 Container Image Build

- Please go ../scripts/build.all.images dir, the building settings are in docker-compose.yaml.
- There are two different images from the same source code: "ekba-ui" and "ekba-ui-mini", one for regular UI and the other for mini UI
- Before docker building, need to prepare .env and .env.mini files respectively for these two images: copy from env.example and update it with actual values.
