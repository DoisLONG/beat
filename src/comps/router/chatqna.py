# Copyright (C) 2024 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

import os

from comps import ChatQnAGateway, MicroService, ServiceOrchestrator, ServiceType

MEGA_SERVICE_HOST_IP = os.getenv("MEGA_SERVICE_HOST_IP", "0.0.0.0")
MEGA_SERVICE_PORT = int(os.getenv("MEGA_SERVICE_PORT", 8888))
EMBEDDING_SERVICE_HOST_IP = os.getenv("EMBEDDING_SERVICE_HOST_IP", "0.0.0.0")
EMBEDDING_SERVICE_PORT = int(os.getenv("EMBEDDING_SERVICE_PORT", 6000))
RETRIEVER_SERVICE_HOST_IP = os.getenv("RETRIEVER_SERVICE_HOST_IP", "0.0.0.0")
RETRIEVER_SERVICE_PORT = int(os.getenv("RETRIEVER_SERVICE_PORT", 7000))
RERANK_SERVICE_HOST_IP = os.getenv("RERANK_SERVICE_HOST_IP", "0.0.0.0")
RERANK_SERVICE_PORT = int(os.getenv("RERANK_SERVICE_PORT", 8000))
LLM_SERVICE_HOST_IP = os.getenv("LLM_SERVICE_HOST_IP", "0.0.0.0")
LLM_SERVICE_PORT = int(os.getenv("LLM_SERVICE_PORT", 9000))
WEB_SEARCH_SERVICE_HOST_IP = os.getenv("WEB_SEARCH_HOST_IP", "0.0.0.0")
WEB_SEARCH_SERVICE_PORT = int(os.getenv("WEB_SEARCH_PORT", 7050))
MCP_SERVICE_HOST_IP = os.getenv("MCP_SERVICE_HOST_IP", "0.0.0.0")
MCP_SERVICE_PORT = int(os.getenv("MCP_SERVICE_PORT", 9999))
ENABLE_RERANK = os.getenv("ENABLE_RERANK", "true").lower() == "true"


class ChatQnAService:
    def __init__(self, host="0.0.0.0", port=8000):
        self.host = host
        self.port = port
        self.megaservice = ServiceOrchestrator()

    def add_remote_service(self):
        embedding = MicroService(
            name="embedding",
            host=EMBEDDING_SERVICE_HOST_IP,
            port=EMBEDDING_SERVICE_PORT,
            endpoint="/v1/embeddings",
            use_remote_service=True,
            service_type=ServiceType.EMBEDDING,
        )
        retriever = MicroService(
            name="retriever",
            host=RETRIEVER_SERVICE_HOST_IP,
            port=RETRIEVER_SERVICE_PORT,
            endpoint="/v1/retrieval",
            use_remote_service=True,
            service_type=ServiceType.RETRIEVER,
        )
        llm = MicroService(
            name="llm",
            host=LLM_SERVICE_HOST_IP,
            port=LLM_SERVICE_PORT,
            endpoint="/v1/chat/completions",
            use_remote_service=True,
            service_type=ServiceType.LLM,
        )
        mcp = MicroService(
            name="mcp",
            host=MCP_SERVICE_HOST_IP,
            port=MCP_SERVICE_PORT,
            endpoint="/v1/mcp",
            use_remote_service=True,
            service_type=ServiceType.MCP,
        )

        if ENABLE_RERANK:
            rerank = MicroService(
                name="rerank",
                host=RERANK_SERVICE_HOST_IP,
                port=RERANK_SERVICE_PORT,
                endpoint="/v1/reranking",
                use_remote_service=True,
                service_type=ServiceType.RERANK,
            )
            # Service configuration with rerank enabled
            self.megaservice.add(embedding).add(retriever).add(rerank).add(mcp).add(llm)
            self.megaservice.flow_to(embedding, retriever)
            self.megaservice.flow_to(retriever, rerank)
            self.megaservice.flow_to(rerank, llm)
            self.megaservice.flow_to(mcp, llm)
        else:
            # Service configuration with rerank disabled
            self.megaservice.add(embedding).add(retriever).add(llm)
            self.megaservice.flow_to(embedding, retriever)
            self.megaservice.flow_to(retriever, llm)

        self.gateway = ChatQnAGateway(megaservice=self.megaservice, host="0.0.0.0", port=self.port)


if __name__ == "__main__":
    chatqna = ChatQnAService(host=MEGA_SERVICE_HOST_IP, port=MEGA_SERVICE_PORT)
    chatqna.add_remote_service()
