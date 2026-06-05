# Copyright (C) 2024 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

import json

import bson.errors as BsonError
from bson import json_util
from bson.objectid import ObjectId
from comps.chathistory.config import COLLECTION_NAME
from comps.chathistory.mongo_conn import MongoClient


class DocumentStore:

    def __init__(
        self,
        user: str,
    ):
        self.user = user

    def initialize_storage(self) -> None:
        self.db_client = MongoClient.get_db_client()
        self.collection = self.db_client[COLLECTION_NAME]

    async def save_document(self, document):
        """Stores a new document into the storage.

        Args:
            document: The document to be stored.

        Returns:
            str: The ID of the inserted document.

        Raises:
            Exception: If an error occurs while storing the document.
        """
        try:
            inserted_conv = await self.collection.insert_one(
                document.model_dump(by_alias=True, mode="json", exclude={"id"})
            )
            document_id = str(inserted_conv.inserted_id)
            return document_id

        except Exception as e:
            print(e)
            raise Exception(e)

    async def update_document(self, document_id, updated_data, first_query, last_query_trace_data, current_prompt_only, source_file_name) -> str:
        """Updates a document in the collection with the given document_id.

        Args:
            document_id (str): The ID of the document to update.
            updated_data (object): The updated data to be set in the document.
            first_query (object): The first query to be set in the document.
            last_query_trace_data (List[TraceInfo]): The trace data to be set in the document.
            current_prompt_only (bool): Whether the current prompt is without history.

        Returns:
            bool: True if the document was successfully updated, False otherwise.

        Raises:
            KeyError: If an invalid document_id is provided.
            Exception: If an error occurs during the update process.
        """
        try:
            _id = ObjectId(document_id)
            update_result = await self.collection.update_one(
                {"_id": _id, "data.user": self.user},
                {"$set": {
                    "data": updated_data.model_dump(by_alias=True, mode="json"),
                    "first_query": first_query,
                    "last_query_trace_data": last_query_trace_data,
                    "current_prompt_only": current_prompt_only,
                    "source_file_name": source_file_name
                }}
            )
            if update_result.modified_count == 1:
                return "Updated document : {}".format(document_id)
            else:
                raise Exception("Not able to Update the Document")

        except BsonError.InvalidId as e:
            print(e)
            raise KeyError(e)
        except Exception as e:
            print(e)
            raise Exception(e)

    async def update_document_feedback(self, document_id, update_message_index, feedback) -> str:
        """Updates the feedback of a specific message in the document.

        Args:
            document_id (str): The ID of the document to update.
            update_message_index (int): The index of the message to update.
            feedback (str): The new feedback to set for the message.

        Returns:
            str: A message indicating the result of the update.

        Raises:
            KeyError: If an invalid document_id is provided.
            Exception: If an error occurs during the update process.
        """
        try:
            _id = ObjectId(document_id)
            update_query = {
                "$set": {f"data.messages.{update_message_index}.feedback": feedback}
            }
            update_result = await self.collection.update_one(
                {"_id": _id, "data.user": self.user},
                update_query
            )
            if update_result.modified_count == 1:
                return "Updated document field : {}".format(document_id)
            else:
                raise Exception("Not able to Update the Document Field")

        except BsonError.InvalidId as e:
            print(e)
            raise KeyError(e)
        except Exception as e:
            print(e)
            raise e

    async def get_all_documents_of_user(self) -> list[dict]:
        """Retrieves all documents of a specific user from the collection.

        Returns:
            A list of dictionaries representing the conversation documents.
        Raises:
            Exception: If there is an error while retrieving the documents.
        """
        conversation_list: list = []
        try:
            cursor = self.collection.find({"data.user": self.user}, {"data": 0})

            async for document in cursor:
                document["id"] = str(document["_id"])
                del document["_id"]
                conversation_list.append(document)
            return conversation_list

        except Exception as e:
            print(e)
            raise Exception(e)

    async def get_all_documents_of_user_and_file(self, source_file_name) -> list[dict]:
        """Retrieves all documents of a specific user from the collection,
        filtered by source_file_name, and returns only id, create_time, and first_query fields.

        Returns:
            A list of dictionaries representing the filtered conversation documents
            with only id, create_time, and first_query fields.

        Raises:
            Exception: If there is an error while retrieving the documents.
        """
        conversation_list: list = []
        try:
            # 查询条件：匹配用户和source_file_name
            query = {"data.user": self.user, "source_file_name": source_file_name}

            # 投影：只返回_id, create_time, 和 first_query 字段
            projection = {"_id": 1, "create_time": 1, "first_query": 1}

            cursor = self.collection.find(query, projection)

            async for document in cursor:
                # 将 _id 转换为 id
                document["id"] = str(document["_id"])
                del document["_id"]
                conversation_list.append(document)

            return conversation_list

        except Exception as e:
            print(e)
            raise Exception(e)


    async def get_user_documents_by_id(self, document_id) -> dict | None:
        """Retrieves a user document from the collection based on the given document ID.

        Args:
            document_id (str): The ID of the document to retrieve.

        Returns:
            dict | None: The user document if found, None otherwise.
        """
        try:
            _id = ObjectId(document_id)
            response: dict | None = await self.collection.find_one({"_id": _id, "data.user": self.user})
            if response:
                del response["_id"]
                return response["data"]
            return None

        except BsonError.InvalidId as e:
            print(e)
            raise KeyError(e)

        except Exception as e:
            print(e)
            raise Exception(e)

    async def delete_document(self, document_id) -> str:
        """Deletes a document from the collection based on the provided document ID.

        Args:
            document_id (str): The ID of the document to be deleted.

        Returns:
            bool: True if the document is successfully deleted, False otherwise.

        Raises:
            KeyError: If the provided document ID is invalid.
            Exception: If an error occurs during the deletion process.
        """

        try:
            _id = ObjectId(document_id)
            delete_result = await self.collection.delete_one({"_id": _id, "data.user": self.user})

            delete_count = delete_result.deleted_count
            print(f"Deleted {delete_count} documents!")

            if delete_count == 1:
                return "Deleted document : {}".format(document_id)
            else:
                raise Exception("Not able to delete the Document")

        except BsonError.InvalidId as e:
            print(e)
            raise KeyError(e)

        except Exception as e:
            print(e)
            raise Exception(e)

    async def get_user_documents_by_source_file_name(self, source_file_name) -> dict | None:
        """Retrieves a user document from the collection based on the given source_file_name.

                Args:
                    source_file_name (str)： The source file name of the document to retrieve.

                Returns:
                    dict | None: The user document if found, None otherwise.
                """
        try:
            response: dict | None = await self.collection.find_one({"source_file_name": source_file_name, "data.user": self.user})
            if response:
                del response["_id"]
                return response["data"]
            return None

        except BsonError.InvalidId as e:
            print(e)
            raise KeyError(e)

        except Exception as e:
            print(e)
            raise Exception(e)
