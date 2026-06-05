# Copyright (C) 2024 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

from typing import Any, Dict, List, Optional, Union

import numpy as np
from docarray import BaseDoc, DocList
from docarray.documents import AudioDoc
from docarray.typing import AudioUrl, ImageUrl
from pydantic import Field, conint, conlist, field_validator,BaseModel
from comps.cores.proto.api_protocol import StreamOptions


class TopologyInfo:
    # will not keep forwarding to the downstream nodes in the black list
    # should be a pattern string
    downstream_black_list: Optional[list] = []


class TextDoc(BaseDoc, TopologyInfo):
    text: str = None

class McpDoc(TextDoc):
    text:str
    mcp_list: List[str]


class MetadataTextDoc(TextDoc):
    metadata: Optional[Dict[str, Any]] = Field(
        description="This encloses all metadata associated with the textdoc.",
        default=None,
    )


class ImageDoc(BaseDoc):
    url: Optional[ImageUrl] = Field(
        description="The path to the image. It can be remote (Web) URL, or a local file path",
        default=None,
    )
    base64_image: Optional[str] = Field(
        description="The base64-based encoding of the image",
        default=None,
    )


class TextImageDoc(BaseDoc):
    image: ImageDoc = None
    text: TextDoc = None


MultimodalDoc = Union[
    TextDoc,
    ImageDoc,
    TextImageDoc,
]


class Base64ByteStrDoc(BaseDoc):
    byte_str: str


class DocPath(BaseDoc):
    path: str
    chunk_size: int = 1500
    chunk_overlap: int = 100
    process_table: bool = False
    table_strategy: str = "fast"
    pdf_ocr_type: int = 0
    collection_name: str


class EmbedDoc(BaseDoc):
    text: str
    embedding: conlist(float, min_length=0)
    search_type: str = "similarity_score_threshold"
    k: int = 4
    distance_threshold: Optional[float] = None
    fetch_k: int = 20
    lambda_mult: float = 0.5
    score_threshold: float = 0.5
    constraints: Optional[Union[Dict[str, Any], None]] = None
    collection_name: Optional[str] = None


class EmbedMultimodalDoc(EmbedDoc):
    # extend EmbedDoc with these attributes
    url: Optional[ImageUrl] = Field(
        description="The path to the image. It can be remote (Web) URL, or a local file path.",
        default=None,
    )
    base64_image: Optional[str] = Field(
        description="The base64-based encoding of the image.",
        default=None,
    )


class Audio2TextDoc(AudioDoc):
    url: Optional[AudioUrl] = Field(
        description="The path to the audio.",
        default=None,
    )
    model_name_or_path: Optional[str] = Field(
        description="The Whisper model name or path.",
        default="openai/whisper-small",
    )
    language: Optional[str] = Field(
        description="The language that Whisper prefer to detect.",
        default="auto",
    )

# retrieval -> llm/rerank
class SearchedDoc(BaseDoc):
    retrieved_docs: DocList[MetadataTextDoc]
    initial_query: str
    top_n: int = 1

    # Add LLM parameters
    model: Optional[str] = None  # for openai and ollama
    max_tokens: int = 0
    max_new_tokens: int = 1024
    top_k: int = 10
    top_p: float = 0.95
    typical_p: float = 0.95
    temperature: float = 0.01
    frequency_penalty: float = 0.0
    presence_penalty: float = 0.0
    repetition_penalty: float = 1.03
    streaming: bool = True
    stream_options: Optional[StreamOptions] = None

    chat_template: Optional[str] = Field(
        default=None,
        description=(
            "A template to use for this conversion. "
            "If this is not passed, the model's default chat template will be "
            "used instead. We recommend that the template contains {context} and {question} for rag,"
            "or only contains {question} for chat completion without rag."
        ),
    )

    class Config:
        json_encoders = {np.ndarray: lambda x: x.tolist()}


class SearchedMultimodalDoc(SearchedDoc):
    metadata: List[Dict[str, Any]]


class LVMSearchedMultimodalDoc(SearchedMultimodalDoc):
    max_new_tokens: conint(ge=0, le=1024) = 512
    top_k: int = 10
    top_p: float = 0.95
    typical_p: float = 0.95
    temperature: float = 0.01
    streaming: bool = False
    repetition_penalty: float = 1.03
    chat_template: Optional[str] = Field(
        default=None,
        description=(
            "A template to use for this conversion. "
            "If this is not passed, the model's default chat template will be "
            "used instead. We recommend that the template contains {context} and {question} for multimodal-rag on videos."
        ),
    )


class GeneratedDoc(BaseDoc):
    text: str
    prompt: str


class RerankedDoc(BaseDoc):
    reranked_docs: DocList[TextDoc]
    initial_query: str

# rerank -> llm
class LLMParamsDoc(BaseDoc):
    model: Optional[str] = None  # for openai and ollama
    query: str
    max_tokens: int = 0
    max_new_tokens: int = 1024
    top_k: int = 10
    top_p: float = 0.95
    typical_p: float = 0.95
    temperature: float = 0.01
    frequency_penalty: float = 0.0
    presence_penalty: float = 0.0
    repetition_penalty: float = 1.03
    streaming: bool = True
    stream_options: Optional[StreamOptions] = None

    chat_template: Optional[str] = Field(
        default=None,
        description=(
            "A template to use for this conversion. "
            "If this is not passed, the model's default chat template will be "
            "used instead. We recommend that the template contains {context} and {question} for rag,"
            "or only contains {question} for chat completion without rag."
        ),
    )
    documents: Optional[
        List[Union[str, Dict[str, Union[str, Dict[str, Any]]]]]
    ] = Field(
        default=[],
        description=(
            "A list of dicts representing documents that will be accessible to "
            "the model if it is performing RAG (retrieval-augmented generation)."
            " If the template does not support RAG, this argument will have no "
            "effect. We recommend that each document should be a dict containing "
            '"title" and "text" keys.'
        ),
    )

    @field_validator("chat_template")
    def chat_template_must_contain_variables(cls, v):
        return v

# mega gateway pipeline
class LLMParams(BaseDoc):
    max_tokens: int = 0
    max_new_tokens: int = 1024
    top_k: int = 10
    top_p: float = 0.95
    typical_p: float = 0.95
    temperature: float = 0.01
    frequency_penalty: float = 0.0
    presence_penalty: float = 0.0
    repetition_penalty: float = 1.03
    streaming: bool = True
    stream_options: Optional[StreamOptions] = None

    chat_template: Optional[str] = Field(
        default=None,
        description=(
            "A template to use for this conversion. "
            "If this is not passed, the model's default chat template will be "
            "used instead. We recommend that the template contains {context} and {question} for rag,"
            "or only contains {question} for chat completion without rag."
        ),
    )


class RetrieverParms(BaseDoc):
    search_type: str = "similarity"
    k: int = 4
    distance_threshold: Optional[float] = None
    fetch_k: int = 20
    lambda_mult: float = 0.5
    score_threshold: float = 0.2

    collection_name: Optional[str] = None


class RerankerParms(BaseDoc):
    top_n: int = 1

class McpParms(BaseDoc):
    mcp_list:List[str] = []

class RAGASParams(BaseDoc):
    questions: DocList[TextDoc]
    answers: DocList[TextDoc]
    docs: DocList[TextDoc]
    ground_truths: DocList[TextDoc]


class RAGASScores(BaseDoc):
    answer_relevancy: float
    faithfulness: float
    context_recallL: float
    context_precision: float


class GraphDoc(BaseDoc):
    text: str
    strtype: Optional[str] = Field(
        description="type of input query, can be 'query', 'cypher', 'rag'",
        default="query",
    )
    max_new_tokens: Optional[int] = Field(default=1024)
    rag_index_name: Optional[str] = Field(default="rag")
    rag_node_label: Optional[str] = Field(default="Task")
    rag_text_node_properties: Optional[list] = Field(default=["name", "description", "status"])
    rag_embedding_node_property: Optional[str] = Field(default="embedding")


class LVMDoc(BaseDoc):
    image: str
    prompt: str
    max_new_tokens: conint(ge=0, le=1024) = 512
    top_k: int = 10
    top_p: float = 0.95
    typical_p: float = 0.95
    temperature: float = 0.01
    repetition_penalty: float = 1.03
    streaming: bool = False


class LVMVideoDoc(BaseDoc):
    video_url: str
    chunk_start: float
    chunk_duration: float
    prompt: str
    max_new_tokens: conint(ge=0, le=1024) = 512

class FakeTextContent(BaseModel):
    text: str
    type: str


class FakeToolContent(BaseModel):
    type: str
    name: str
    input: dict


class ToolCallResult(BaseModel):
    type: str
    result: Union[FakeTextContent, FakeToolContent, List[FakeToolContent]]
    node_number: int = 0


class ToolResultItem(BaseModel):
    name: str = ""
    result: str = ""


class UserQuery(BaseModel):
    user_input: str = ""
    tool_chain: List[str] = []
    tool_result: List[ToolResultItem] = []

class ToolResult(BaseModel):
    type: str
    query: str
    generate_info: dict
    prompt:str
    tool_infos:List

class McpResultRequest(BaseModel):
    type: str
    query: str
    generate_info: dict
    prompt: str
    max_tokens: int
    max_new_tokens: int
    top_k: int
    top_p: float
    typical_p: float
    temperature: float
    frequency_penalty: float
    presence_penalty: float
    repetition_penalty: float
    streaming: bool = True
    stream_options: StreamOptions= None
    chat_template: Optional[str] = ""
    documents: Optional[
        List[Union[str, Dict[str, Union[str, Dict[str, Any]]]]]
    ] = Field(
        default=[],
        description=(
            "A list of dicts representing documents that will be accessible to "
            "the model if it is performing RAG (retrieval-augmented generation)."
            " If the template does not support RAG, this argument will have no "
            "effect. We recommend that each document should be a dict containing "
            '"title" and "text" keys.'
        ),
    )

class TrainParams(BaseDoc):
    messages: List[dict[str, Any]]
    session_id: str
    max_tokens: int = 0
    max_new_tokens: int = 1024
    top_k: int = 10
    top_p: float = 0.95
    typical_p: float = 0.95
    temperature: float = 0.01
    frequency_penalty: float = 0.0
    presence_penalty: float = 0.0
    repetition_penalty: float = 1.03
    streaming: bool = True
    stream_options: Optional[StreamOptions] = None
