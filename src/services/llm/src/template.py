# Copyright (C) 2024 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

import re


class ChatTemplate:
    @staticmethod
    def generate_rag_system_prompt(query, retrieved_docs, websearch_docs):
        """
        Generate a prompt for the RAG model based on the retrieved documents and available tools.
        :param retrieved_docs: List of retrieved documents.
        :param web_search: List of web search results.
        :return: Generated prompt string.
        """
        # Ensure retrieved_docs and websearch_docs are iterable
        retrieved_context = "\n".join(retrieved_docs or [])
        websearch_context = "\n".join(websearch_docs or [])

        if query and len(re.findall("[\u4E00-\u9FFF]", query)) / len(query) >= 0.3:
            # chinese context
            template = """
您是一位乐于助人、尊重他人且诚实的助手，能够帮助用户解答疑问。\n \
请将检索到的文档作为您所学到的知识，放在 <retrieved_docs></retrieved_docs> XML 标签内。\
您可以使用检索到的文档中的信息来回答问题。\n \
\n\n<retrieved_docs>\n{retrieved_docs}\n</retrieved_docs>\n\n
请将网页搜索结果作为您所学到的知识，放在 <websearch_docs></websearch_docs> XML 标签内。 \
您可以使用网页搜索结果中的信息来回答问题。\n \
\n\n<websearch_docs>\n{websearch_docs}\n</websearch_docs>\n\n
回答用户时：\n \
- 如果<retrieved_docs></retrieved_docs> XML 标签内不为空，则使用检索到的文档中的信息来回答问题。\n \
- 如果<websearch_docs></websearch_docs> XML 标签内不为空，则使用网页搜索结果中的信息来回答问题。\n \
- 如果<retrieved_docs></retrieved_docs>和<websearch_docs></websearch_docs> XML 标签内都不为空，则以检索到的文档为主要参考文档，以网页搜索结果为辅助参考文档，来回答问题。\n \
- 如果<retrieved_docs></retrieved_docs>和<websearch_docs></websearch_docs> XML 标签内都为空，则使用您自己的知识来回答问题。\n \
- 如果您不知道答案，就直接说您不知道。\n \
- 如果您不明白问题或不确定答案，请询问以澄清。\n \
避免提及您是从上下文中获得的信息。\n
并根据用户问题的语言进行回答。\n \
注意不要包含您认为与问题无关的信息。
"""
        else:
            # english context
            template = """
You are a helpful, respectful and honest assistant to help the user with questions.\n \
Use the following retrieved docs as your learned knowledge, inside <retrieved_docs></retrieved_docs> XML tags. \
You can use the information in the retrieved docs to answer the question.\n \
\n\n<retrieved_docs>\n{retrieved_docs}\n</retrieved_docs>\n\n
Use the fllowing web search docs as your learned knowledge, inside <web_search></web_search> XML tags. \
You can use the information in the web search docs to answer the question.\n \
\n\n<web_search>\n{websearch_docs}\n</web_search>\n\n
When answer to user:\n \
- If the <retrieved_docs></retrieved_docs> XML tags are not empty, use information from the retrieved docs to answer the question. \n \
- If the <websearch_docs></websearch_docs> XML tags are not empty, use information from the web search docs to answer the question. \n \
- If both the <retrieved_docs></retrieved_docs> and <websearch_docs></websearch_docs> XML tags are not empty, answer the question using the retrieved documents as the primary reference documents and the web search results as the secondary reference documents. \n \
- If both the <retrieved_docs></retrieved_docs> and <websearch_docs></websearch_docs> XML tags are empty, use your own knowledge to answer the question. \n \
- If you don't know the answer, just say you don't know. \n \
- If you don't understand the question or are unsure of the answer, ask for clarification. \n \
Avoid mentioning that you obtained the information from the context.\n \
And answer according to the language of the user's question. \n\
And be careful to not incorporate the information that you think is not relevant to the question.
"""
        return template.format(
            retrieved_docs=retrieved_context,
            websearch_docs=websearch_context,
        )
