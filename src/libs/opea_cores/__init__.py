# Copyright (C) 2024 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

# Document
from .proto.docarray import (
    Audio2TextDoc,
    Base64ByteStrDoc,
    DocPath,
    EmbedDoc,
    GeneratedDoc,
    LLMParamsDoc,
    SearchedDoc,
    SearchedMultimodalDoc,
    LVMSearchedMultimodalDoc,
    RerankedDoc,
    TextDoc,
    MetadataTextDoc,
    RAGASParams,
    RAGASScores,
    GraphDoc,
    LVMDoc,
    LVMVideoDoc,
    ImageDoc,
    TextImageDoc,
    MultimodalDoc,
    EmbedMultimodalDoc,
)
from .proto.api_protocol import (
    ChatCompletionRequest
)

# Constants
from .mega.constants import MegaServiceEndpoint, ServiceRoleType, ServiceType

# Microservice
from .mega.orchestrator import ServiceOrchestrator
from .mega.micro_service import MicroService, register_microservice, opea_microservices
from .mega.gateway import (
    Gateway,
    ChatQnAGateway,
)

# Statistics
from .mega.base_statistics import statistics_dict, register_statistics

# Logger
from .mega.logger import CustomLogger
