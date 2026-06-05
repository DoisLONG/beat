# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

from enum import Enum

class PromptKey(str, Enum):
    """
    功能类型枚举
    """
    CONSTRAINTS_GET_KNOWLEDGE_POINT_EXCEL_235B = "get_knowledge_point_excel"
    CONSTRAINTS_GET_KNOWLEDGE_POINT_WORD_235B = "get_knowledge_point_word"
    KNOWLEDGE_FOCUS_STEP_235B = "step"
    KNOWLEDGE_FOCUS_ERROR_235B = "error"
    KNOWLEDGE_FOCUS_DATA_235B = "data"
    CONSTRAINTS_GENERATE_KNOWLEDGE_POINT_EXCEL_235B = "knowledge_point_excel_generate"
    CONSTRAINTS_GENERATE_KNOWLEDGE_POINT_WORD_235B = "knowledge_point_word_generate"

    # 内容加载部分提示词
    GET_EXCEL_HEAD_AND_CONTENT_235B = "excel_structure"
    GET_FILE_LANGUAGE_TYPE_235B = "file_language"

    # 通用 Excel QA 生成提示词
    MAKE_UNIVERSAL_EXCEL_QA_235B = "universal_excel_qa"
    BACKSTORY_GENERATE_EXCEL_235B = "backstory_excel_generate"
    GET_UNIVERSAL_EXCEL_KNOWLEDGE_235B = "universal_excel_knowledge"

    # 操作规程 QA 生成提示词
    MAKE_OPERATION_MULTI_QA_235B = "operation_multi_qa"
    BACKSTORY_GENERATE_WORD_235B = "backstory_word_generate"
    GET_UNIVERSAL_WORD_KNOWLEDGE_235B = "universal_word_knowledge"




class Lang(str, Enum):
    """
    语种类型枚举
    """
    ZH = "zh"
    EN = "en"
    TH = "th"

class PromptRegistry:
    """
    Prompt注册器
    """
    _data: dict = {}

    @classmethod
    def register(cls, key: PromptKey, lang: Lang, template: str):
        cls._data.setdefault(key, {})[lang] = template

    @classmethod
    def get(cls, key: PromptKey, lang: Lang, **kwargs):
        try:
            template = cls._data[key][lang]
        except KeyError:
            raise ValueError(f"Prompt not found: {key} - {lang}")
        return template.format(**kwargs)

# 这是注册方式，根据功能模块和语种、具体提示词进行注册
# PromptRegistry.register(
#     PromptKey.SUMMARY,
#     Lang.ZH,
#     "请用专业且易懂的语言总结以下内容：\n{content}"
# )
#
# 这是使用方式，其中question和content都是在PromptKey.QA和Lang.EN两者确定的提示词中占位符的替换
# prompt = PromptRegistry.get(
#     PromptKey.QA,
#     Lang.EN,
#     question="What is RAG?",
#     context="RAG stands for Retrieval-Augmented Generation..."
# )

