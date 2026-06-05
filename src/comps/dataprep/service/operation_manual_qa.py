# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
import asyncio
import json
import os
import re
import math
from bs4 import BeautifulSoup
from openai import OpenAI
from comps import CustomLogger
from comps.dataprep.config import (
    DATAPREP_QA_CONCURRENCY_LIMIT,
    get_dataprep_llm_config,
    get_llm_extra_body,
)
from comps.dataprep.service.generation_constraint_qa import generate_word_chapter_qa_prompts
from comps.dataprep.prompt.prompt_manager import PromptRegistry, PromptKey, Lang
from comps.dataprep.utils import build_chapters, extract_json_from_response, clean_prefix

logger = CustomLogger("operation_manual_qa", "INFO")
INVALID_VALUES = ["", "/", None]
# 新增全局题量目标与补充轮次
TOTAL_ROUNDS = int(os.getenv("TOTAL_ROUNDS", 10))
MAX_SUPPLEMENT_ROUNDS = int(os.getenv("MAX_SUPPLEMENT_ROUNDS", 3))
MAX_CHAPTER_TEXT_LEN = int(os.getenv("DATAPREP_OP_QA_CHAPTER_MAX_LEN", "4000"))
MAX_BACKGROUND_CHUNK_LEN = int(os.getenv("DATAPREP_OP_QA_BACKGROUND_CHUNK_MAX_LEN", "4000"))
CONCURRENCY_LIMIT = DATAPREP_QA_CONCURRENCY_LIMIT
HTML_FRAGMENT_PATTERN = re.compile(r"(?is)<(html|table)\b.*?>.*?</\1>")
HTML_TAG_HINT_PATTERN = re.compile(r"(?is)</?(html|body|table|tr|td|th|p|div|span|br)\b")

# ====================== 数据结构工具函数 ======================

def compress_text(text: str, max_sentences: int = 5) -> str:
    """压缩文本，截取前后部分"""
    import re
    sentences = re.split(r'[\n。；]', text)
    sentences = [s.strip() for s in sentences if s.strip()]
    if len(sentences) <= 2 * max_sentences:
        return "\n".join(sentences)
    else:
        return "\n".join(sentences[:max_sentences] + sentences[-max_sentences:])


def split_batches(row: dict, batch_size: int = 2000) -> list:
    """将操作规程长文本分批"""
    compressed_fields = []
    for key, value in row.items():
        if isinstance(value, list):
            for idx, item in enumerate(value):
                compressed_fields.append(f"{key}[{idx+1}]: {compress_text(str(item))}")
        elif isinstance(value, dict):
            compressed_fields.append(f"{key}: {compress_text(json.dumps(value, ensure_ascii=False))}")
        else:
            if value not in INVALID_VALUES:
                compressed_fields.append(f"{key}: {compress_text(str(value))}")

    full_text = "\n".join(compressed_fields)
    n_batches = math.ceil(len(full_text) / batch_size)
    return [full_text[i * batch_size:(i + 1) * batch_size] for i in range(n_batches)]


def split_text_by_max_len(text: str, max_len: int = MAX_CHAPTER_TEXT_LEN) -> list[str]:
    """按长度切分章节正文，优先按行边界切，避免中间截断语义。"""
    if not text:
        return []
    if len(text) <= max_len:
        return [text]

    chunks = []
    current_lines = []
    current_len = 0
    for line in text.splitlines(keepends=True):
        line_len = len(line)
        if line_len > max_len:
            if current_lines:
                chunks.append("".join(current_lines).strip())
                current_lines = []
                current_len = 0
            start = 0
            while start < line_len:
                chunks.append(line[start:start + max_len].strip())
                start += max_len
            continue

        if current_lines and current_len + line_len > max_len:
            chunks.append("".join(current_lines).strip())
            current_lines = [line]
            current_len = line_len
        else:
            current_lines.append(line)
            current_len += line_len

    if current_lines:
        chunks.append("".join(current_lines).strip())

    return [chunk for chunk in chunks if chunk]


def pack_texts_by_max_len(texts: list[str], max_len: int) -> list[str]:
    """将多个文本按最大长度打包，避免后续汇总时再次超长。"""
    batches: list[str] = []
    current_parts: list[str] = []
    current_len = 0

    for text in texts:
        for segment in split_text_by_max_len(text.strip(), max_len):
            clean_text = segment.strip()
            if not clean_text:
                continue

            part = clean_text if not current_parts else f"\n\n{clean_text}"
            part_len = len(part)
            if current_parts and current_len + part_len > max_len:
                batches.append("".join(current_parts))
                current_parts = [clean_text]
                current_len = len(clean_text)
            else:
                current_parts.append(part)
                current_len += part_len

    if current_parts:
        batches.append("".join(current_parts))

    return batches


def _clean_html_content(text: str) -> str:
    if not text:
        return ""
    if "<" not in text or ">" not in text:
        return text

    def _replace_fragment(match: re.Match[str]) -> str:
        return _html_fragment_to_text(match.group(0))

    cleaned = HTML_FRAGMENT_PATTERN.sub(_replace_fragment, text)
    if HTML_TAG_HINT_PATTERN.search(cleaned):
        soup = BeautifulSoup(cleaned, "html.parser")
        cleaned = soup.get_text("\n", strip=True)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()


def _html_fragment_to_text(fragment: str) -> str:
    soup = BeautifulSoup(fragment, "html.parser")
    table_texts: list[str] = []

    for table in soup.find_all("table"):
        rows: list[str] = []
        for tr in table.find_all("tr"):
            cells = tr.find_all(["th", "td"])
            cell_texts = [
                re.sub(r"\s+", " ", cell.get_text(" ", strip=True)).strip()
                for cell in cells
            ]
            cell_texts = [value for value in cell_texts if value]
            if cell_texts:
                rows.append(" | ".join(cell_texts))
        if rows:
            table_texts.append("\n".join(rows))
        table.extract()

    residual = soup.get_text("\n", strip=True)
    parts = [part for part in [residual, *table_texts] if part]
    return "\n".join(parts)


# ====================== 操作规程问答生成 ======================

async def make_multi_qa_prompt_operation(row: dict, client: OpenAI,filename: str, user_prompt: str = "", min_pairs: int = 1, total_rows: int = 1, lang: str = "zh") -> list[str]:
    """
    操作规程文件问答对生成 Prompt（支持压缩 + 分批）
    使用注册器模式获取多语言提示词模板
    增加：全局最小题量 TOTAL_ROUNDS 与本行最低组数 M (一组=问答+填空)。
    """
    # 将行数据转换为文本
    # content_text = row_to_text(row)
    chapters = build_chapters([row])

    chapter_title = chapters[0]["title"]
    full_text = chapters[0]["full_text"]
    chapter_chunks = split_text_by_max_len(full_text, MAX_CHAPTER_TEXT_LEN)
    if len(chapter_chunks) > 1:
        logger.info(f"章节正文过长，按 {MAX_CHAPTER_TEXT_LEN} 字切分为 {len(chapter_chunks)} 片")

    llm_config = get_dataprep_llm_config()
    model_name = llm_config.model
    extra_body = get_llm_extra_body(model_name)
    async def build_prompt(chapter_text: str) -> str:
        identify_prompt = PromptRegistry.get(
            PromptKey.GET_UNIVERSAL_WORD_KNOWLEDGE_235B,
            Lang(lang),
            chapter_title=chapter_title,
            chapter_text=chapter_text
        )
        res = await asyncio.to_thread(
            client.chat.completions.create,
            model=model_name,
            messages=[{"role": "user", "content": identify_prompt}],
            extra_body=extra_body,
            temperature=0.3
        )
        try:
            knowledge_list = extract_json_from_response(res.choices[0].message.content)
        except ValueError as exc:
            logger.warning(f"操作规程知识点提取结果不是有效JSON，当前分片按空知识点处理: {exc}")
            knowledge_list = []

        if isinstance(knowledge_list, dict):
            if isinstance(knowledge_list.get("knowledge_list"), list):
                knowledge_list = knowledge_list.get("knowledge_list")
            elif isinstance(knowledge_list.get("knowledge_infos"), list):
                knowledge_list = knowledge_list.get("knowledge_infos")
            else:
                knowledge_list = []

        if not isinstance(knowledge_list, list):
            logger.warning("操作规程知识点提取结果不是数组，当前分片按空知识点处理")
            knowledge_list = []

        prompt = PromptRegistry.get(
            PromptKey.MAKE_OPERATION_MULTI_QA_235B,
            Lang(lang),
            chapter_title=chapter_title,
            chapter_text=chapter_text,
            knowledge_list_json=json.dumps(knowledge_list, ensure_ascii=False, indent=2)
        )
        if lang == "th":
            prompt += f"\n【ข้อกำหนดเพิ่มเติม】 “โปรดใช้ภาษาไทยสำหรับเนื้อหาโจทย์และคำตอบ” \n {user_prompt}\n\n"
        elif lang == "en":
            prompt += f"\n【Additional Requirements】Please use English for both the question stem and the answer content. \n{user_prompt}\n\n"
        else:
            prompt += f"\n【补充要求】题干和答案文本内容请使用中文 \n {user_prompt}\n\n"

        return prompt

    prompts = await asyncio.gather(*(build_prompt(chapter_text) for chapter_text in chapter_chunks))
    return [prompt for prompt in prompts if prompt]


# ====================== 解析模型输出 ======================

def _extract_qa_objects(payload: object) -> list[dict]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict):
        for key in ("qa_list", "questions", "items", "data"):
            value = payload.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]
        if payload:
            return [payload]
    return []


def _map_question_type_to_cn(raw_type: object) -> str:
    value = str(raw_type or "").strip().lower().replace("-", "_")
    mapping = {
        "short_answer": "问答题",
        "essay": "问答题",
        "qa": "问答题",
        "问答题": "问答题",
        "fill_in_the_blank": "填空题",
        "fill_blank": "填空题",
        "blank": "填空题",
        "填空题": "填空题",
    }
    return mapping.get(value, "")

def parse_operation_qa_response(text: str, row: dict, filename: str) -> list:
    """
    解析操作规程问答对输出
    """
    text = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL)
    try:
        payload = extract_json_from_response(text)
    except ValueError as exc:
        logger.warning(f"操作规程题目解析失败，模型未返回有效JSON: {exc}")
        return []

    qa_objects = _extract_qa_objects(payload)
    results = []

    for qa in qa_objects:
        ques = str(qa.get("question", "")).strip()
        qtype = _map_question_type_to_cn(qa.get("question_type", ""))
        if not ques or not qtype:
            continue

        ques = f"【{os.path.splitext(os.path.basename(filename))[0]}】{ques}"
        raw_answer = qa.get("answer", "")
        if qtype == "问答题":
            if isinstance(raw_answer, list):
                scoring_points = [
                    clean_prefix(str(point).strip())
                    for point in raw_answer
                    if str(point).strip()
                ]
            else:
                scoring_points = [
                    clean_prefix(a)
                    for a in re.split(r'[\n;；]', str(raw_answer))
                    if a.strip()
                ]
            answer_data = str(scoring_points)
        else:
            if isinstance(raw_answer, list):
                answer_data = "；".join(str(a).strip() for a in raw_answer if str(a).strip())
            else:
                answer_data = str(raw_answer).strip()
            if "___" not in ques:
                continue

        try:
            diff_value = float(qa.get("difficulty_factor", qa.get("difficulty", 0.5)))
            diff_value = max(0.0, min(1.0, diff_value))
        except:
            diff_value = 0.5

        qa_item = {
            "题目": ques,
            "题型": qtype,
            "答案": answer_data,
            "难度因子": diff_value,
            "来源字段": row.get("title_content", ""),
            "内容": row_to_text(row),
            "定位": f'{row.get("total_title","")}'
        }
        results.append(qa_item)

    return results


def row_to_text(row: dict, indent: int = 0) -> str:
    """
    将嵌套的操作规程结构化数据转换为多层缩进文本，方便人工或LLM查看生成依据。
    """
    lines = []
    prefix = "  " * indent  # 根据层级增加缩进

    for k, v in row.items():
        if isinstance(v, dict):
            lines.append(f"{prefix}{k}:")
            lines.append(row_to_text(v, indent + 1))
        elif isinstance(v, list):
            if len(v) == 0:
                lines.append(f"{prefix}{k}: []")
            else:
                lines.append(f"{prefix}{k}:")
                for i, item in enumerate(v):
                    lines.append(f"{prefix}  [{i+1}]")
                    if isinstance(item, (dict, list)):
                        lines.append(row_to_text(item, indent + 2))
                    else:
                        lines.append(f"{prefix}    {item}")
        else:
            v_str = _clean_html_content(str(v).strip()).replace("\r", "")
            if "\n" in v_str:
                lines.append(f"{prefix}{k}:")
                for line in v_str.splitlines():
                    line = line.strip()
                    if line:
                        lines.append(f"{prefix}  {line}")
            else:
                lines.append(f"{prefix}{k}: {v_str}")

    return "\n".join(lines)


# ====================== 批量生成逻辑 ======================

async def batch_generate_operation_qa(structured_rows: list, filename: str, client: OpenAI, user_prompt: str,sop_id:int, db_client, lang: str="zh",scope_type:str = "all"):
    all_qa = []
    total_prompt_tokens = 0
    total_completion_tokens = 0
    total_rows = len(structured_rows)
    # 计算每条最低组数（每组2题）
    min_pairs_base = max(1, (TOTAL_ROUNDS + total_rows - 1) // (2 * total_rows))
    semaphore = asyncio.Semaphore(CONCURRENCY_LIMIT)

    async def process_row(idx: int, row: dict) -> tuple[list, int, int]:
        logger.info(f"  处理操作规程第 {idx + 1} 条记录")
        # 跳过“附件”或“附录”章节（title 包含即可）
        skip_keywords = [
            # 中文
            "附件", "附录",
            # 英文
            "appendix", "attachment", "annex",
            # 泰文（常见译法）
            "ภาคผนวก",  # 附录/Appendix
            "สิ่งที่แนบมา",  # 附件/Attachment
            "ภาคผนวกเอกสาร",  # Annex 的表达
        ]
        title = row.get("title_content",  "").strip().lower()
        if any(keyword.lower() in title for keyword in skip_keywords):
            logger.info("跳过 附件/附录 章节")
            return [], 0, 0
        # 生成背景故事
        background_content, prompt_token, completion_token = await generate_operation_qa_background(row_to_text(row), filename, client, lang)
        logger.info(f"  生成背景故事token: prompt:{prompt_token}, completion:{completion_token}")
        if scope_type == "all":
            prompts = await make_multi_qa_prompt_operation(row=row, client=client,filename=filename, user_prompt=user_prompt, min_pairs=min_pairs_base, total_rows=total_rows, lang=lang,)
        else:
            # 做一下格式转化
            prompts = [await generate_word_chapter_qa_prompts([row],client, scope_type,lang=lang)]
        llm_config = get_dataprep_llm_config()
        model_name = llm_config.model
        extra_body = get_llm_extra_body(model_name)
        row_all_qa = []
        row_prompt_tokens = prompt_token
        row_completion_tokens = completion_token
        for prompt in prompts:
            if prompt == "":
                continue
            try:
                response = await asyncio.to_thread(
                    client.chat.completions.create,
                    model=model_name,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.3,
                    max_tokens=4000,
                    extra_body=extra_body
                )

                if hasattr(response, "usage") and response.usage:
                    row_prompt_tokens += response.usage.prompt_tokens
                    row_completion_tokens += response.usage.completion_tokens

                resp_text = response.choices[0].message.content
                qa_list = parse_operation_qa_response(resp_text, row, filename)
                # 添加背景内容到每个 QA 项
                for qa in qa_list:
                    qa["背景"] = background_content
                row_all_qa.extend(qa_list)
                logger.info(f"生成 {len(qa_list)} 道题目")

            except Exception as e:
                logger.info(f"生成失败: {str(e)}")
                continue

        return row_all_qa, row_prompt_tokens, row_completion_tokens

    async def run_row(idx: int, row: dict) -> tuple[list, int, int]:
        async with semaphore:
            return await process_row(idx, row)

    results = await asyncio.gather(*(run_row(idx, row) for idx, row in enumerate(structured_rows)))
    for row_all_qa, row_prompt_tokens, row_completion_tokens in results:
        all_qa.extend(row_all_qa)
        total_prompt_tokens += row_prompt_tokens
        total_completion_tokens += row_completion_tokens

    db_client.update_percent_by_id(sop_id, "80%", lang=lang)
    logger.info("=" * 60)
    logger.info(f"总计生成题目: {len(all_qa)}")
    logger.info(f"Token使用: prompt={total_prompt_tokens}, completion={total_completion_tokens}")
    logger.info("=" * 60)
    return all_qa, total_prompt_tokens, total_completion_tokens


# 根据片段内容内容生成操作规程问答对背景故事
async def _generate_operation_background_once(row: str, filename: str, client: OpenAI, lang: str="zh"):
    """
    根据规程片段内容生成简明背景故事，便于后续问答对补充背景信息。
    :param row: 规程片段内容（已格式化为文本）
    :param filename: 文件名
    :param client: OpenAI 客户端
    :param lang: 语言（"zh"、"en"、"th"）
    :return: 背景故事字符串
    """
    prompt = PromptRegistry.get(PromptKey.BACKSTORY_GENERATE_WORD_235B,Lang(lang),row=row)
    llm_config = get_dataprep_llm_config()
    model_name = llm_config.model
    extra_body = get_llm_extra_body(model_name)
    try:
        response = await asyncio.to_thread(
            client.chat.completions.create,
            model=model_name,
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
            max_tokens=2000,
            extra_body=extra_body
        )
        background = response.choices[0].message.content.strip()
        if hasattr(response, "usage") and response.usage:
            completion_token = response.usage.completion_tokens
            prompt_token = response.usage.prompt_tokens
        else:
            completion_token = 0
            prompt_token = 0
        return background, prompt_token, completion_token
    except Exception as e:
        logger.error(f"生成操作规程背景失败: {e}")
        return "", 0, 0


async def generate_operation_qa_background(row: str, filename: str, client: OpenAI, lang: str="zh"):
    """按分片生成并分层汇总操作规程背景，避免长章节输入超过模型限制。"""
    chunks = split_text_by_max_len(row, MAX_BACKGROUND_CHUNK_LEN)
    if not chunks:
        return "", 0, 0

    if len(chunks) > 1:
        logger.info(
            f"操作规程背景输入较长，按 {MAX_BACKGROUND_CHUNK_LEN} 字切分为 {len(chunks)} 片后生成背景"
        )

    total_prompt_tokens = 0
    total_completion_tokens = 0
    current_texts = chunks

    while True:
        next_texts: list[str] = []
        batches = pack_texts_by_max_len(current_texts, MAX_BACKGROUND_CHUNK_LEN)
        for batch in batches:
            background, prompt_token, completion_token = await _generate_operation_background_once(
                batch,
                filename,
                client,
                lang,
            )
            total_prompt_tokens += prompt_token
            total_completion_tokens += completion_token
            if background.strip():
                next_texts.append(background.strip())

        if not next_texts:
            return "", total_prompt_tokens, total_completion_tokens
        if len(next_texts) == 1:
            return next_texts[0], total_prompt_tokens, total_completion_tokens
        current_texts = [f"片段{i + 1}背景:\n{text}" for i, text in enumerate(next_texts)]
