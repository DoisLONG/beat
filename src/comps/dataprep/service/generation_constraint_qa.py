# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

import asyncio
import json

from openai import OpenAI

from comps.dataprep.config import get_dataprep_llm_config, get_llm_extra_body
from comps.dataprep.prompt.prompt_manager import PromptRegistry, PromptKey, Lang
from comps.dataprep.utils import extract_json_from_response, build_chapters


async def make_excel_qa_constraint_prompt(row: dict, client: OpenAI, user_prompt: str = "", lang: str = "zh",
                                          scope_type: str = "all"):
    """
    基于Excel行内容在相关约束下问答对
    第一步：先判断此行知识点是否具备过滤策略的要点，没有就跳过此行知识点，并标注
    第二步：根据上一步过滤好的标注知识点进行题目输出
    """
    knowledge_info = await filter_knowledge_point_by_strategy(client, row, scope_type, lang)
    prompt = ""
    if knowledge_info is not None and knowledge_info['is_matched'] and knowledge_info["knowledge_infos"]:
        prompt = PromptRegistry.get(PromptKey.CONSTRAINTS_GENERATE_KNOWLEDGE_POINT_EXCEL_235B,
                                    Lang(lang),
                                    question_strategy=knowledge_info['knowledge_type'],
                                    knowledge_point_infos=json.dumps(knowledge_info["knowledge_infos"],
                                                                     ensure_ascii=False),
                                    excel_row_json=json.dumps(row, ensure_ascii=False)
                                    )
    return prompt


async def filter_knowledge_point_by_strategy(client: OpenAI, row: dict, scope_type: str = "all", lang: str = "zh"):
    """
    先判断此行知识点是否具备过滤策略的要点，没有就跳过此行知识点，并标注
    """
    strategy = PromptRegistry.get(PromptKey(scope_type), Lang(lang))
    prompt = PromptRegistry.get(PromptKey.CONSTRAINTS_GET_KNOWLEDGE_POINT_EXCEL_235B, Lang(lang), strategy=strategy,
                                excel_row_json=json.dumps(row, ensure_ascii=False))

    llm_config = get_dataprep_llm_config()
    extra_body = get_llm_extra_body(llm_config.model)

    res = await asyncio.to_thread(
        client.chat.completions.create,
        model=llm_config.model,
        messages=[{"role": "user", "content": prompt}],
        extra_body=extra_body,
        temperature=0.3
    )
    content = res.choices[0].message.content
    # 进行JSON转化
    result = extract_json_from_response(content)
    return result





# ----------------------------------------- 以下是word的--------------------------------------------------


async def generate_word_chapter_qa_prompts(word_tree, client, scope_type="all", lang="zh"):
    chapters = build_chapters(word_tree)
    strategy = PromptRegistry.get(PromptKey(scope_type), Lang(lang))
    identify_prompt = PromptRegistry.get(PromptKey.CONSTRAINTS_GET_KNOWLEDGE_POINT_WORD_235B,
                                         Lang(lang), strategy=strategy,
                                         chapter_title=chapters[0]["title"],
                                         chapter_text=chapters[0]["full_text"])

    llm_config = get_dataprep_llm_config()
    extra_body = get_llm_extra_body(llm_config.model)

    res = await asyncio.to_thread(
        client.chat.completions.create,
        model=llm_config.model,
        messages=[{"role": "user", "content": identify_prompt}],
        extra_body=extra_body,
        temperature=0.3
    )
    knowledge_list = extract_json_from_response(res.choices[0].message.content)

    prompts = build_multi_qa_prompt(chapters[0], knowledge_list, lang) if knowledge_list else ""

    return prompts


def build_multi_qa_prompt(chapter, knowledge_list, lang):
    prompt = PromptRegistry.get(
        PromptKey.CONSTRAINTS_GENERATE_KNOWLEDGE_POINT_WORD_235B, Lang(lang),
        chapter_title=chapter["title"],
        chapter_text=chapter["full_text"],
        knowledge_list_json=json.dumps(knowledge_list, ensure_ascii=False, indent=2))
    return prompt
