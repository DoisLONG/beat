# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

import re

from comps.chathistory.config import USER_LOGS_COLLECTION_NAME
from comps.chathistory.mongo_conn import MongoClient
from comps.chathistory.mongo_store import DocumentStore
from typing import Optional, Dict, Any, List
from datetime import datetime


class AnswerLogDocumentStore(DocumentStore):
    """
    专门用于答题日志的文档存储类
    """

    def __init__(self, user: str):
        super().__init__(user)
        self.user = user

    async def initialize_storage(self):
        self.db_client = MongoClient.get_db_client()
        self.collection = self.db_client[USER_LOGS_COLLECTION_NAME]
        await self.collection.create_index([("user_id", 1)])
        await self.collection.create_index([("exams_id", 1)])
        await self.collection.create_index([("created_at", -1)])

    async def save_user_log(self, user_log_data: Dict[str, Any]) -> str:
        document = {
            "user_id": user_log_data.get("user_id"),
            "exams_id": user_log_data.get("exams_id"),
            "created_at": datetime.utcnow()
        }
        # 透传 smart 多语种字段（data_lang 控制业务数据路由；prompt_lang 控制 prompt/判题文案）
        if "data_lang" in user_log_data:
            document["data_lang"] = user_log_data.get("data_lang")
        if "prompt_lang" in user_log_data:
            document["prompt_lang"] = user_log_data.get("prompt_lang")
        if "logs" in user_log_data:
            # 全流程日志
            document.update({
                "logs": user_log_data["logs"],
                "start_time": user_log_data.get("start_time"),
                "end_time": user_log_data.get("end_time"),
            })
        else:
            # 单题日志
            document.update({
                "question": user_log_data.get("question"),
                "user_answer": user_log_data.get("user_answer"),
                "answer_time": user_log_data.get("answer_time"),
                "exam_time": user_log_data.get("exam_time"),
                "decision_result": user_log_data.get("decision_result"),
                "source_file_name": user_log_data.get("source_file_name"),
            })
        result = await self.collection.insert_one(document)
        return str(result.inserted_id)

    async def query_user_logs(
            self,
            user_id: str,
            exams_id: Optional[str] = None,
            question: Optional[str] = None,
            log_type: Optional[str] = None  #"single" 或 "full"
    ) -> List[Dict[str, Any]]:
        query = {"user_id": user_id}
        if exams_id:
            query["exams_id"] = exams_id
        # 确保只查询单题日志（包含 question 字段的文档）
        if log_type == "single":
            query["question"] = {"$exists": True}
            if question is not None:
                escaped_question = re.escape(question)
                query["$and"] = [
                    {"question": {"$exists": True}},
                    {"question": {"$regex": escaped_question, "$options": "i"}}
                ]
        elif log_type == "full":
            query["logs"] = {"$exists": True}
        cursor = self.collection.find(query).sort("created_at", -1)
        logs = []
        async for doc in cursor:
            doc['_id'] = str(doc['_id'])
            logs.append(doc)
        return logs

    async def delete_user_logs(self, user_id: str, exams_id: Optional[str] = None) -> int:
        query = {"user_id": user_id}
        if exams_id:
            query["exams_id"] = exams_id
        result = await self.collection.delete_many(query)
        return result.deleted_count