# Copyright (C) 2024 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
import os
from datetime import datetime
from typing import Optional, Any, Dict, List
from xmlrpc.client import DateTime

from fastapi import HTTPException

from comps.chathistory.user_logs_mongo_store import AnswerLogDocumentStore
from mongo_store import DocumentStore
from pydantic import BaseModel

from comps import CustomLogger
from comps.cores.mega.micro_service import opea_microservices, register_microservice
from comps.cores.proto.api_protocol import ChatCompletionRequest

logger = CustomLogger("chathistory_mongo", os.getenv("LOG_LEVEL", "INFO"))

class ChatMessage(BaseModel):
    data: ChatCompletionRequest
    first_query: Optional[str] = None
    id: Optional[str] = None
    last_query_trace_data: Optional[List[Dict[str, Any]]] = None
    current_prompt_only: Optional[bool] = True
    source_file_name: Optional[str] = None
    create_time: Optional[str] = None

class ChatId(BaseModel):
    user: str
    id: Optional[str] = None
    source_file_name: Optional[str] = None

class Feedback(BaseModel):
    user: str
    id: str
    feedback: str
    update_message_index: int

def get_first_string(value):
    if isinstance(value, str):
        return value
    elif isinstance(value, list):
        # Assuming we want the first string from the first dictionary
        if value and isinstance(value[0], dict):
            first_dict = value[0]
            if first_dict:
                # Get the first value from the dictionary
                first_key = next(iter(first_dict))
                return first_dict[first_key]


@register_microservice(
    name="opea_service@chathistory_mongo",
    endpoint="/v1/chathistory/create",
    host="0.0.0.0",
    input_datatype=ChatMessage,
    port=6022,
)
async def create_documents(document: ChatMessage):
    """Creates or updates a document in the document store.

    Args:
        document (ChatMessage): The ChatMessage object containing the data to be stored.

    Returns:
        The result of the operation if successful, None otherwise.
    """
    logger.debug(f"document: {document}")

    try:
        if document.data.user is None:
            raise HTTPException(status_code=500, detail="Please provide the user information")
        store = DocumentStore(document.data.user)
        store.initialize_storage()
        if document.first_query is None:
            document.first_query = get_first_string(document.data.messages)
        # Extract last_query_trace_data and current_prompt_only from document.data
        if hasattr(document.data, 'last_query_trace_data'):
            document.last_query_trace_data = document.data.last_query_trace_data
        if hasattr(document.data, 'current_prompt_only'):
            document.current_prompt_only = document.data.current_prompt_only
        if document.id:
            res = await store.update_document(
                document.id,
                document.data,
                document.first_query,
                document.last_query_trace_data,
                document.current_prompt_only,
                document.source_file_name
            )
        else:
            document.create_time = datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S")
            res = await store.save_document(document)

        logger.debug(f"results: {res}")
        return res

    except Exception as e:
        # Handle the exception here
        logger.info(f"An error occurred: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@register_microservice(
    name="opea_service@chathistory_mongo",
    endpoint="/v1/chathistory/feedback/update",
    host="0.0.0.0",
    input_datatype=Feedback,
    port=6022,
)
async def update_feedback(document: Feedback):
    """Update user feedback in the document store.

    Args:
        document (Feedback): The Feedback object containing the data to be stored.

    Returns:
        The result of the operation if successful, None otherwise.
    """
    logger.debug(f"document: {document}")

    try:
        if document.user is None:
            raise HTTPException(status_code=500, detail="Please provide the user information")
        if document.id is None:
            raise HTTPException(status_code=400, detail="Document ID is required for update")
        if document.update_message_index is None or document.feedback is None:
            raise HTTPException(status_code=400, detail="Message index and feedback are required for update")
        
        store = DocumentStore(document.user)
        store.initialize_storage()
        
        res = await store.update_document_feedback(
            document.id,
            document.update_message_index,
            document.feedback
        )

        logger.debug(f"results: {res}")
        return res

    except HTTPException as e:
        raise e
    except Exception as e:
        # Handle the exception here
        logger.error(f"An error occurred: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@register_microservice(
    name="opea_service@chathistory_mongo",
    endpoint="/v1/chathistory/get",
    host="0.0.0.0",
    input_datatype=ChatId,
    port=6022,
)
async def get_documents(document: ChatId):
    """Retrieves documents from the document store based on the provided ChatId.

    Args:
        document (ChatId): The ChatId object containing the user and optional document id.

    Returns:
        The retrieved documents if successful, None otherwise.
    """
    logger.debug(f"document: {document}")

    try:
        store = DocumentStore(document.user)
        store.initialize_storage()
        if document.source_file_name is not None:
            res = await store.get_user_documents_by_source_file_name(document.source_file_name)
        elif document.id is None:
            res = await store.get_all_documents_of_user()
        else:
            res = await store.get_user_documents_by_id(document.id)
        logger.debug(f"results: {res}")
        return {"status": "200", "result": res}
    except Exception as e:
        # Handle the exception here
        logger.info(f"An error occurred: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@register_microservice(
    name="opea_service@chathistory_mongo",
    endpoint="/v1/chathistory/list",
    host="0.0.0.0",
    input_datatype=ChatId,
    port=6022,
)
async def list_documents(document: ChatId):
    """Lists all documents in the document store for a given user.

    Args:
        document (ChatId): The ChatId object containing the user.

    Returns:
        The list of documents if successful, None otherwise.
    """
    logger.debug(f"document: {document}")

    try:
        store = DocumentStore(document.user)
        store.initialize_storage()
        res = await store.get_all_documents_of_user_and_file(document.source_file_name)
        logger.debug(f"results: {res}")
        return {"status": "200", "result": res}
    except Exception as e:
        # Handle the exception here
        logger.info(f"An error occurred: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@register_microservice(
    name="opea_service@chathistory_mongo",
    endpoint="/v1/chathistory/delete",
    host="0.0.0.0",
    input_datatype=ChatId,
    port=6022,
)
async def delete_documents(document: ChatId):
    """Deletes a document from the document store based on the provided ChatId.

    Args:
        document (ChatId): The ChatId object containing the user and document id.

    Returns:
        The result of the deletion if successful, None otherwise.
    """
    logger.debug(f"document: {document}")

    try:
        store = DocumentStore(document.user)
        store.initialize_storage()
        if document.id is None:
            raise Exception("Document id is required.")
        else:
            res = await store.delete_document(document.id)

        logger.debug(f"results: {res}")
        return res

    except Exception as e:
        # Handle the exception here
        logger.info(f"An error occurred: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    opea_microservices["opea_service@chathistory_mongo"].start()
