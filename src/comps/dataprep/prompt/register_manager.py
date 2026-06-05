# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

from comps.dataprep.prompt.prefix.load_file_content_prompt import GET_EXCEL_HEAD_AND_DATA_PROMPT_ZH, \
    GET_EXCEL_HEAD_AND_DATA_PROMPT_TH, GET_EXCEL_HEAD_AND_DATA_PROMPT_EN, GET_FILE_LANG_PROMPT_ZH
from comps.dataprep.prompt.prompt_manager import PromptRegistry, PromptKey, Lang
from comps.dataprep.prompt.prefix.question_constraints_prompt import total_knowledge_constraint_prompt_template, \
    total_knowledge_constraint_prompt_template_en, total_knowledge_constraint_prompt_template_th, step_strategy_prompt, \
    step_strategy_prompt_th, step_strategy_prompt_en, data_strategy_prompt, data_strategy_prompt_en, \
    data_strategy_prompt_th, error_strategy_prompt, error_strategy_prompt_en, error_strategy_prompt_th, \
    generate_constraint_qa_prompt, generate_constraint_qa_prompt_en, generate_constraint_qa_prompt_th, \
    WORD_CHAPTER_KNOWLEDGE_PROMPT, WORD_CHAPTER_KNOWLEDGE_PROMPT_EN, WORD_CHAPTER_KNOWLEDGE_PROMPT_TH, \
    GENERATE_WORD_CHAPTER_MULTI_QA_PROMPT, GENERATE_WORD_CHAPTER_MULTI_QA_PROMPT_EN, \
    GENERATE_WORD_CHAPTER_MULTI_QA_PROMPT_TH
from comps.dataprep.prompt.prefix.qa_generate_prompt_excel import make_universal_excel_qa_prompt_zh, \
    make_universal_excel_qa_prompt_en, make_universal_excel_qa_prompt_th, BACKSTORY_GENERATE_PROMPT_EXCEL_ZH, \
    BACKSTORY_GENERATE_PROMPT_EXCEL_TH, BACKSTORY_GENERATE_PROMPT_EXCEL_EN, universal_excel_knowledge_prompt_zh, \
    universal_excel_knowledge_prompt_en, universal_excel_knowledge_prompt_th
from comps.dataprep.prompt.prefix.qa_generate_word_prompt import MAKE_OPERATION_QA_PROMPT_ZH, \
    MAKE_OPERATION_QA_PROMPT_EN, MAKE_OPERATION_QA_PROMPT_TH, BACKSTORY_GENERATE_PROMPT_WORD_ZH, \
    BACKSTORY_GENERATE_PROMPT_WORD_TH, BACKSTORY_GENERATE_PROMPT_WORD_EN, universal_word_knowledge_prompt_zh, \
    universal_word_knowledge_prompt_en, universal_word_knowledge_prompt_th

#-------------------------------------QA生成时，知识侧重点生成提示词注册器-------------------------------------
PromptRegistry.register(
    PromptKey.CONSTRAINTS_GET_KNOWLEDGE_POINT_EXCEL_235B,
    Lang.ZH,
    total_knowledge_constraint_prompt_template
)

PromptRegistry.register(
    PromptKey.CONSTRAINTS_GET_KNOWLEDGE_POINT_EXCEL_235B,
    Lang.EN,
    total_knowledge_constraint_prompt_template_en
)

PromptRegistry.register(
    PromptKey.CONSTRAINTS_GET_KNOWLEDGE_POINT_EXCEL_235B,
    Lang.TH,
    total_knowledge_constraint_prompt_template_th
)

PromptRegistry.register(
    PromptKey.KNOWLEDGE_FOCUS_STEP_235B,
    Lang.ZH,
    step_strategy_prompt
)

PromptRegistry.register(
    PromptKey.KNOWLEDGE_FOCUS_STEP_235B,
    Lang.EN,
    step_strategy_prompt_en
)

PromptRegistry.register(
    PromptKey.KNOWLEDGE_FOCUS_STEP_235B,
    Lang.TH,
    step_strategy_prompt_th
)

PromptRegistry.register(
    PromptKey.KNOWLEDGE_FOCUS_DATA_235B,
    Lang.ZH,
    data_strategy_prompt
)

PromptRegistry.register(
    PromptKey.KNOWLEDGE_FOCUS_DATA_235B,
    Lang.EN,
    data_strategy_prompt_en
)

PromptRegistry.register(
    PromptKey.KNOWLEDGE_FOCUS_DATA_235B,
    Lang.TH,
    data_strategy_prompt_th
)

PromptRegistry.register(
    PromptKey.KNOWLEDGE_FOCUS_ERROR_235B,
    Lang.ZH,
    error_strategy_prompt
)

PromptRegistry.register(
    PromptKey.KNOWLEDGE_FOCUS_ERROR_235B,
    Lang.EN,
    error_strategy_prompt_en
)

PromptRegistry.register(
    PromptKey.KNOWLEDGE_FOCUS_ERROR_235B,
    Lang.TH,
    error_strategy_prompt_th
)

PromptRegistry.register(
    PromptKey.CONSTRAINTS_GENERATE_KNOWLEDGE_POINT_EXCEL_235B,
    Lang.ZH,
    generate_constraint_qa_prompt
)

PromptRegistry.register(
    PromptKey.CONSTRAINTS_GENERATE_KNOWLEDGE_POINT_EXCEL_235B,
    Lang.EN,
    generate_constraint_qa_prompt_en
)

PromptRegistry.register(
    PromptKey.CONSTRAINTS_GENERATE_KNOWLEDGE_POINT_EXCEL_235B,
    Lang.TH,
    generate_constraint_qa_prompt_th
)

PromptRegistry.register(
    PromptKey.CONSTRAINTS_GET_KNOWLEDGE_POINT_WORD_235B,
    Lang.ZH,
    WORD_CHAPTER_KNOWLEDGE_PROMPT
)

PromptRegistry.register(
    PromptKey.CONSTRAINTS_GET_KNOWLEDGE_POINT_WORD_235B,
    Lang.EN,
    WORD_CHAPTER_KNOWLEDGE_PROMPT_EN
)

PromptRegistry.register(
    PromptKey.CONSTRAINTS_GET_KNOWLEDGE_POINT_WORD_235B,
    Lang.TH,
    WORD_CHAPTER_KNOWLEDGE_PROMPT_TH
)

PromptRegistry.register(
    PromptKey.CONSTRAINTS_GENERATE_KNOWLEDGE_POINT_WORD_235B,
    Lang.ZH,
    GENERATE_WORD_CHAPTER_MULTI_QA_PROMPT
)

PromptRegistry.register(
    PromptKey.CONSTRAINTS_GENERATE_KNOWLEDGE_POINT_WORD_235B,
    Lang.EN,
    GENERATE_WORD_CHAPTER_MULTI_QA_PROMPT_EN
)

PromptRegistry.register(
    PromptKey.CONSTRAINTS_GENERATE_KNOWLEDGE_POINT_WORD_235B,
    Lang.TH,
    GENERATE_WORD_CHAPTER_MULTI_QA_PROMPT_TH
)

#-------------------------------------内容加载国际化提示词注册器-------------------------------------

PromptRegistry.register(
    PromptKey.GET_EXCEL_HEAD_AND_CONTENT_235B,
    Lang.ZH,
    GET_EXCEL_HEAD_AND_DATA_PROMPT_ZH
)

PromptRegistry.register(
    PromptKey.GET_EXCEL_HEAD_AND_CONTENT_235B,
    Lang.TH,
    GET_EXCEL_HEAD_AND_DATA_PROMPT_TH
)

PromptRegistry.register(
    PromptKey.GET_EXCEL_HEAD_AND_CONTENT_235B,
    Lang.EN,
    GET_EXCEL_HEAD_AND_DATA_PROMPT_EN
)

PromptRegistry.register(
    PromptKey.GET_FILE_LANGUAGE_TYPE_235B,
    Lang.ZH,
    GET_FILE_LANG_PROMPT_ZH
)

#-------------------------------------通用 Excel QA 生成提示词注册器-------------------------------------

PromptRegistry.register(
    PromptKey.GET_UNIVERSAL_EXCEL_KNOWLEDGE_235B,
    Lang.ZH,
    universal_excel_knowledge_prompt_zh
)

PromptRegistry.register(
    PromptKey.GET_UNIVERSAL_EXCEL_KNOWLEDGE_235B,
    Lang.EN,
    universal_excel_knowledge_prompt_en
)

PromptRegistry.register(
    PromptKey.GET_UNIVERSAL_EXCEL_KNOWLEDGE_235B,
    Lang.TH,
    universal_excel_knowledge_prompt_th
)






PromptRegistry.register(
    PromptKey.MAKE_UNIVERSAL_EXCEL_QA_235B,
    Lang.ZH,
    make_universal_excel_qa_prompt_zh
)

PromptRegistry.register(
    PromptKey.MAKE_UNIVERSAL_EXCEL_QA_235B,
    Lang.EN,
    make_universal_excel_qa_prompt_en
)

PromptRegistry.register(
    PromptKey.MAKE_UNIVERSAL_EXCEL_QA_235B,
    Lang.TH,
    make_universal_excel_qa_prompt_th
)

PromptRegistry.register(
    PromptKey.BACKSTORY_GENERATE_EXCEL_235B,
    Lang.ZH,
    BACKSTORY_GENERATE_PROMPT_EXCEL_ZH
)

PromptRegistry.register(
    PromptKey.BACKSTORY_GENERATE_EXCEL_235B,
    Lang.TH,
    BACKSTORY_GENERATE_PROMPT_EXCEL_TH
)

PromptRegistry.register(
    PromptKey.BACKSTORY_GENERATE_EXCEL_235B,
    Lang.EN,
    BACKSTORY_GENERATE_PROMPT_EXCEL_EN
)

#-------------------------------------操作规程 QA 生成提示词注册器-------------------------------------
PromptRegistry.register(
    PromptKey.GET_UNIVERSAL_WORD_KNOWLEDGE_235B,
    Lang.ZH,
    universal_word_knowledge_prompt_zh
)

PromptRegistry.register(
    PromptKey.GET_UNIVERSAL_WORD_KNOWLEDGE_235B,
    Lang.EN,
    universal_word_knowledge_prompt_en
)

PromptRegistry.register(
    PromptKey.GET_UNIVERSAL_WORD_KNOWLEDGE_235B,
    Lang.TH,
    universal_word_knowledge_prompt_th
)








PromptRegistry.register(
    PromptKey.MAKE_OPERATION_MULTI_QA_235B,
    Lang.ZH,
    MAKE_OPERATION_QA_PROMPT_ZH
)

PromptRegistry.register(
    PromptKey.MAKE_OPERATION_MULTI_QA_235B,
    Lang.EN,
    MAKE_OPERATION_QA_PROMPT_EN
)

PromptRegistry.register(
    PromptKey.MAKE_OPERATION_MULTI_QA_235B,
    Lang.TH,
    MAKE_OPERATION_QA_PROMPT_TH
)

PromptRegistry.register(
    PromptKey.BACKSTORY_GENERATE_WORD_235B,
    Lang.ZH,
    BACKSTORY_GENERATE_PROMPT_WORD_ZH
)

PromptRegistry.register(
    PromptKey.BACKSTORY_GENERATE_WORD_235B,
    Lang.TH,
    BACKSTORY_GENERATE_PROMPT_WORD_TH
)

PromptRegistry.register(
    PromptKey.BACKSTORY_GENERATE_WORD_235B,
    Lang.EN,
    BACKSTORY_GENERATE_PROMPT_WORD_EN
)
