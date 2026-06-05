# Copyright (C) 2024 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

import io
import logging
import os
from functools import lru_cache
from typing import Any, List

import pandas as pd
from fastapi import HTTPException

logger = logging.getLogger(__name__)

# 缓存配置
COLUMN_MAPPING_CACHE_SIZE = 50

# ==================== 列名映射 ====================
# COLUMN_ALIASES = {
#     "阶段": "阶段",
#     "步骤序号": "步骤序号",
#     "步骤\n序号": "步骤序号",
#     "作业点": "作业点",
#     "作业事项任务": "作业事项任务",
#     "所需材料物品等": "所需材料物品等",
#     "所需材料\n物品等": "所需材料物品等",
#     "所需物料品等": "所需材料物品等",
#     "作业标准1-文字说明-具体做什么(动作分解)": "具体做什么",
#     # "具体做什么(动作分解)":"具体做什么",
#     "作业标准1-文字说明-具体做什么\n(动作分解)": "具体做什么",
#     "作业标准1-文字说明-做到什么程度(数据定标)": "做到什么程度",
#     # "做到什么程度(数据定标)": "做到什么程度",
#     "作业标准1-文字说明-特别风险": "特别风险",
#     "作业标准1-文字说明-特别\n风险": "特别风险",
#     "作业标准1-文字说明-特别风险管控": "特别风险管控",
# }
#
# # ====== 列名模版表 ======
# COLUMN_TEMPLATE = {
#     "阶段": "阶段",
#     "步骤序号": "步骤序号",
#     "作业点": "作业点",
#     "作业事项任务": "作业事项任务",
#     "所需材料物品等": "所需材料物品等",  # 保留原键作为基准
#     "作业标准1-文字说明-具体做什么(动作分解)": "具体做什么",
#     "作业标准1-文字说明-做到什么程度(数据定标)": "做到什么程度",
#     "作业标准1-文字说明-特别风险": "特别风险",
#     "作业标准1-文字说明-特别风险管控": "特别风险管控",
# }
#
# # 定义"所需材料物品等"的所有可能合法名称
# MATERIAL_COLUMN_VARIANTS = ["所需材料物品等", "所需物料品等"]


def clean_punctuation(s):
    """清除字符串首尾的中英文逗号、句号及其他特殊字符"""
    # 1. 优先去除首尾的中英文逗号和句号
    # 包含：英文逗号(,)、中文逗号(，)、英文句号(.)、中文句号(。)
    punctuation = ',.，。'
    s_cleaned = str(s).strip(punctuation)

    # 2. 最终去除首尾空格
    return s_cleaned.strip()


def flatten_columns(columns):
    """展平多级列名，同时清理首尾标点"""
    flattened = []
    for col in columns:
        if isinstance(col, tuple):
            clean_parts = [str(c).replace("\n", "").strip() for c in col if c and "Unnamed" not in str(c)]
            col_name = "-".join(clean_parts)
        else:
            col_name = str(col).replace("\n", "").strip()
        flattened.append(col_name)
    return flattened


@lru_cache(maxsize=COLUMN_MAPPING_CACHE_SIZE)
def get_column_mapping_cached(column_tuple):
    """缓存列映射结果"""
    columns = list(column_tuple)
    flattened = []
    for col in columns:
        if isinstance(col, tuple):
            clean_parts = [str(c).replace("\n", "").strip() for c in col if c and "Unnamed" not in str(c)]
            col_name = "-".join(clean_parts)
        else:
            col_name = str(col).replace("\n", "").strip()
        flattened.append(col_name)
    return flattened


def validate_headers(file_name, file_contents):
    """校验表头是否符合作业流程表格的预期要求，同时检查文件格式"""
    try:
        ext = os.path.splitext(file_name)[1].lower()
        # 尝试读取Excel文件，如果失败则说明格式不正确
        if ext in [".xlsx", ".xls"]:
            df = pd.read_excel(io.BytesIO(file_contents), header=[2, 3])
    except Exception as e:
        error_msg = f"文件格式不正确，请上传xlsx或xls格式的Excel文件。"
        logger.error(f"文件格式校验失败: {error_msg}。错误详情：{str(e)}")
        raise HTTPException(status_code=400, detail=error_msg)

    # 处理列名（清除首尾标点）
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = flatten_columns(df.columns.values)
    else:
        df.columns = [clean_punctuation(str(c).replace("\n", "")) for c in df.columns]

    # 校验表头是否符合预期要求
    missing_columns = []
    for expected in COLUMN_TEMPLATE:
        if expected == "所需材料物品等":
            if not any(col in df.columns for col in MATERIAL_COLUMN_VARIANTS):
                missing_columns.append(f"所需材料物品等（或所需物料品等）")
        else:
            if expected not in df.columns:
                missing_columns.append(expected)

    if missing_columns:
        error_msg = f"表头不符合要求，缺少必要列：{', '.join(missing_columns)}"
        logger.error(f"表头校验失败: {error_msg}")
        raise HTTPException(status_code=400, detail=error_msg)

    return None


# ==================== Excel 解析函数 ====================
def extract_structured_rows_from_excel(file_contents) -> list[Any]:
    """提取结构化数据"""
    try:
        df = pd.read_excel(io.BytesIO(file_contents), header=[2, 3])
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = flatten_columns(df.columns.values)
        else:
            df.columns = [str(c).replace("\n", "").strip() for c in df.columns]
        df = df.ffill(axis=0)

        structured = []
        for idx, row in df.iterrows():
            row_dict = {}
            for col, alias in COLUMN_ALIASES.items():
                col = col.replace("\n", "").strip()
                matched_col = next((c for c in df.columns if c.startswith(col)), None)
                if matched_col:
                    value = row.get(matched_col, "")
                    if isinstance(value, str):
                        value = value.replace("\n", " ")
                    row_dict[alias] = value
            row_dict["行号"] = idx + 5
            row_dict["内容"] = "；".join(f"{k}:{v}" for k, v in row_dict.items() if k != "行号" and v not in ("", None))
            structured.append(row_dict)
            logger.info(f"当前行内容: {row_dict}")

        logger.info(f"结构化数据行数: {len(structured)}")
        return structured
    except Exception as e:
        logger.error(f"Excel结构化抽取失败: {e}")
        import traceback
        logger.error(f"详细错误信息: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Excel解析失败: {e}")