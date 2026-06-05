# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

import json
import os
import time
import re
from typing import List

from fastapi import HTTPException
from openai import OpenAI

from comps import CustomLogger
from comps.dataprep.config import (
    MODEL_API_KEY,
    MODEL_BASE_URL,
    get_dataprep_llm_config,
    get_llm_extra_body,
    get_client
)
from comps.dataprep.prompt.llm_prompts import get_knowledge_point_extraction_prompt, get_essay_question_prompt, get_gap_filling_question_prompt

# client is removed to prevent stale global usage. Use get_client() instead.
# client = get_client()

logger = CustomLogger("dataprep--content_agent", os.getenv("LOG_LEVEL", "INFO"))

MAX_RETRIES = 3

def extract_knowledge_point(structured_row: dict, min_pairs: int):
    """
    出题点筛选 + 题型判定
    Temperature 设置较低 (0.1) 以保证提取结果的精确和稳定
    """
    prompt = get_knowledge_point_extraction_prompt(structured_row=structured_row, min_pairs=min_pairs)
    return _call_llm_with_retry(prompt, temperature=0.1, task_name="知识点提取")


def build_essay_questions(step1_out: List[dict], background_text: str):
    """
    根据知识点生成问答题（带SOP背景）
    """
    prompt = get_essay_question_prompt(step1_out=step1_out, background_text=background_text)
    return _call_llm_with_retry(prompt, temperature=0.3, task_name="问答题生成")


def build_gap_filling_question(step1_out: List[dict], background_text: str):
    """
    根据知识点生成填空题（带SOP背景）
    """
    prompt = get_gap_filling_question_prompt(step1_out=step1_out, background_text=background_text)
    return _call_llm_with_retry(prompt, temperature=0.3, task_name="填空题生成")


def _call_llm_with_retry(prompt: str, temperature: float, task_name: str = "任务") -> list | dict:
    """
    封装带有重试机制的 LLM 调用和 JSON 解析
    """
    # Use fresh config each time or at least resolve model name
    config = get_dataprep_llm_config()
    model_name = config.model
    extra_body = get_llm_extra_body(model_name)
    llm_client = get_client() # Uses cached resolver, but potentially updated

    for attempt in range(MAX_RETRIES):
        try:
            res = llm_client.chat.completions.create(
                model=model_name,
                messages=[{"role": "user", "content": prompt}],
                temperature=temperature,
                extra_body=extra_body
            )
            content = res.choices[0].message.content
            
            # 如果是重试，记录一下
            if attempt > 0:
                logger.info(f"[{task_name}] 第 {attempt + 1} 次尝试，模型返回长度: {len(content)}")

            result = extract_response_without_thinking(content)
            
            if result is not None: 
                return result
            
        except Exception as e:
            logger.warning(f"[{task_name}] 第 {attempt + 1}/{MAX_RETRIES} 次尝试失败: {e}")
            if attempt < MAX_RETRIES - 1:
                time.sleep(1)
            else:
                logger.error(f"[{task_name}] 最终失败，返回空列表。")
    
    return []


def extract_json_from_response(response_text: str) -> dict | list:
    """
    从响应文本中提取 JSON 内容
    增强了对非 Markdown 格式 JSON 的提取能力
    """
    try:
        response_text = response_text.strip()
        
        # 1. 尝试提取 Markdown 代码块
        if "```json" in response_text:
            json_start = response_text.find("```json") + 7
            json_end = response_text.find("```", json_start)
            content = response_text[json_start:json_end].strip()
            return json.loads(content)
        elif "```" in response_text:
            json_start = response_text.find("```") + 3
            json_end = response_text.find("```", json_start)
            content = response_text[json_start:json_end].strip()
            return json.loads(content)
            
        # 2. 正则表达式寻找 JSON 结构
        # 匹配列表 [...]
        list_match = re.search(r'^\s*\[.*\]\s*$', response_text, re.DOTALL)
        if list_match:
            return json.loads(list_match.group(0))
            
        # 匹配对象 {...}
        dict_match = re.search(r'^\s*\{.*\}\s*$', response_text, re.DOTALL)
        if dict_match:
            return json.loads(dict_match.group(0))
            
        # 3. 贪婪搜索最外层的 {} 或 []
        start_idx = -1
        end_idx = -1
        
        # 寻找第一个 [ 和 {
        first_bracket = response_text.find('[')
        first_brace = response_text.find('{')
        
        # 确定它是列表还是对象
        if first_bracket != -1 and (first_brace == -1 or first_bracket < first_brace):
             start_idx = first_bracket
             end_idx = response_text.rfind(']') + 1
        elif first_brace != -1:
             start_idx = first_brace
             end_idx = response_text.rfind('}') + 1
             
        if start_idx != -1 and end_idx > start_idx:
            potential_json = response_text[start_idx:end_idx]
            return json.loads(potential_json)

        # 4. 最后尝试直接解析
        return json.loads(response_text)
        
    except Exception as e:
        # 抛出异常以便触发重试
        raise HTTPException(status_code=500, detail=f"JSON 解析失败: {e}")


def extract_response_without_thinking(response_text: str) -> dict | list:
    """
    移除 API 响应中 </think> 标签之前的所有内容，只保留之后的内容，然后提取 JSON
    """
    try:
        # 移除 </think> 之前的思考内容
        if "</think>" in response_text:
            think_end_index = response_text.find("</think>") + len("</think>")
            response_text = response_text[think_end_index:].strip()

        # 调用提取 JSON 的方法
        return extract_json_from_response(response_text)
    except Exception as e:
        # 抛出异常而不是返回空列表，以便触发重试
        raise HTTPException(status_code=500, detail=f"提取响应失败: {e}")


if __name__ == "__main__":
    structured_rows = [
        {
            "作业事项任务": "点检设备",
            "作业标准2-图示(真实比例；拍摄时优选4:3模式)": "=DISPIMG(\"ID_938DDF8AD3DC4631AFABAB549EEE1ECC\",1)",
            "作业点": "深加工车间",
            "做到什么程度(数据定标)": "落球平台放置平稳，辅助站立平台、支撑件、落球圆管齐全，钢球表面光滑无缺损。",
            "具体做什么(动作分解)": "检查落球平台放置是否平稳、配件是否齐全、钢球是否完整无损。",
            "内容": "阶段:作业前；步骤序号:步骤1；作业点:深加工车间；作业事项任务:点检设备；所需材料物品等:落球试验平台、钢球、落球圆管、辅助站立平台；具体做什么(动作分解):检查落球平台放置是否平稳、配件是否齐全、钢球是否完整无损。；做到什么程度(数据定标):落球平台放置平稳，辅助站立平台、支撑件、落球圆管齐全，钢球表面光滑无缺损。；特别风险:/；特别风险管控:/；作业标准2-图示(真实比例；拍摄时优选4:3模式):=DISPIMG(\"ID_938DDF8AD3DC4631AFABAB549EEE1ECC\",1)",
            "所需材料物品等": "落球试验平台、钢球、落球圆管、辅助站立平台",
            "步骤序号": "步骤1",
            "特别风险": "/",
            "特别风险管控": "/",
            "行号": 6,
            "阶段": "作业前"
        },
        {
            "作业事项任务": "选择落球高度和钢球",
            "作业标准2-图示(真实比例；拍摄时优选4:3模式)": "=DISPIMG(\"ID_6DCBAB730B7543CE950F2DA44A62D81F\",1)",
            "作业点": "深加工车间",
            "做到什么程度(数据定标)": "(1)1.2mm：钢球质量为1040g（直径23.5mm）、落球高度为1000mm；(2)5.0mm：钢球质量为227g（直径38.1mm）落球高度为1000mm。",
            "具体做什么(动作分解)": "根据试样的厚度选用钢球规格和落球高度。",
            "内容": "阶段:作业中；步骤序号:步骤2；作业点:深加工车间；作业事项任务:选择落球高度和钢球；所需材料物品等:落球试验平台、钢球、落球圆管；具体做什么(动作分解):根据试样的厚度选用钢球规格和落球高度。；做到什么程度(数据定标):(1)1.2mm：钢球质量为1040g（直径23.5mm）、落球高度为1000mm；(2)5.0mm：钢球质量为227g（直径38.1mm）落球高度为1000mm。；特别风险:/；特别风险管控:/；作业标准2-图示(真实比例；拍摄时优选4:3模式):=DISPIMG(\"ID_6DCBAB730B7543CE950F2DA44A62D81F\",1)",
            "所需材料物品等": "落球试验平台、钢球、落球圆管",
            "步骤序号": "步骤2",
            "特别风险": "/",
            "特别风险管控": "/",
            "行号": 7,
            "阶段": "作业中"
        },
        {
            "作业事项任务": "放入试样",
            "作业标准2-图示(真实比例；拍摄时优选4:3模式)": "=DISPIMG(\"ID_249E30EE95FC49AC9777356EFD4444C4\",1)",
            "作业点": "深加工车间",
            "做到什么程度(数据定标)": "(1)试样放置平稳；(2)落球中心与试样中心点在5mm内。",
            "具体做什么(动作分解)": "(1)打开箱板，将试样抬入落球平台上，绒面朝上，两端放支撑杆上；(2)关闭箱板，确定落球中心位置。",
            "内容": "阶段:作业中；步骤序号:步骤3；作业点:深加工车间；作业事项任务:放入试样；所需材料物品等:手套、试样；具体做什么(动作分解):(1)打开箱板，将试样抬入落球平台上，绒面朝上，两端放支撑杆上；(2)关闭箱板，确定落球中心位置。；做到什么程度(数据定标):(1)试样放置平稳；(2)落球中心与试样中心点在5mm内。；特别风险:破片；特别风险管控:两人协同作业，轻拿轻放；作业标准2-图示(真实比例；拍摄时优选4:3模式):=DISPIMG(\"ID_249E30EE95FC49AC9777356EFD4444C4\",1)",
            "所需材料物品等": "手套、试样",
            "步骤序号": "步骤3",
            "特别风险": "破片",
            "特别风险管控": "两人协同作业，轻拿轻放",
            "行号": 8,
            "阶段": "作业中"
        },
        {
            "作业事项任务": "落球作业",
            "作业标准2-图示(真实比例；拍摄时优选4:3模式)": "=DISPIMG(\"ID_249E30EE95FC49AC9777356EFD4444C4\",1)",
            "作业点": "深加工车间",
            "做到什么程度(数据定标)": "试样破损不超过1片为合格，破损2片需重新取6片试样测试只要再有1片破损即判定为不合格，破损多于或等于3片为不合格。",
            "具体做什么(动作分解)": "每台钢化炉取6片试样，站立辅助平台，在1米的落球圆管上松开钢球，钢球自然下落。",
            "内容": "阶段:作业中；步骤序号:步骤4；作业点:深加工车间；作业事项任务:落球作业；所需材料物品等:落球试验平台、试样、钢球、落球圆管、辅助站立平台；具体做什么(动作分解):每台钢化炉取6片试样，站立辅助平台，在1米的落球圆管上松开钢球，钢球自然下落。；做到什么程度(数据定标):试样破损不超过1片为合格，破损2片需重新取6片试样测试只要再有1片破损即判定为不合格，破损多于或等于3片为不合格。；特别风险:/；特别风险管控:/；作业标准2-图示(真实比例；拍摄时优选4:3模式):=DISPIMG(\"ID_249E30EE95FC49AC9777356EFD4444C4\",1)",
            "所需材料物品等": "落球试验平台、试样、钢球、落球圆管、辅助站立平台",
            "步骤序号": "步骤4",
            "特别风险": "/",
            "特别风险管控": "/",
            "行号": 9,
            "阶段": "作业中"
        },
        {
            "作业事项任务": "异常处理",
            "作业标准2-图示(真实比例；拍摄时优选4:3模式)": "=DISPIMG(\"ID_249E30EE95FC49AC9777356EFD4444C4\",1)",
            "作业点": "深加工车间",
            "做到什么程度(数据定标)": "(1)15分钟内未得到整改，质检班长报告深加工品质管控专员；20分钟未得到整改，质检班长报告体系品质管控专员；100分钟未得到整改，质检班长报告质管工段长。(2)隔离做好记录。",
            "具体做什么(动作分解)": "(1)发现落球冲击不合格，1分钟内通知质检班长和深加工班长处理；(2)追溯上一次检验正常后到本次检验异常时生产的所有产品，将异常品隔离。",
            "内容": "阶段:作业中；步骤序号:步骤5；作业点:深加工车间；作业事项任务:异常处理；所需材料物品等:对讲机、返工记录表；具体做什么(动作分解):(1)发现落球冲击不合格，1分钟内通知质检班长和深加工班长处理；(2)追溯上一次检验正常后到本次检验异常时生产的所有产品，将异常品隔离。；做到什么程度(数据定标):(1)15分钟内未得到整改，质检班长报告深加工品质管控专员；20分钟未得到整改，质检班长报告体系品质管控专员；100分钟未得到整改，质检班长报告质管工段长。(2)隔离做好记录。；特别风险:/；特别风险管控:/；作业标准2-图示(真实比例；拍摄时优选4:3模式):=DISPIMG(\"ID_249E30EE95FC49AC9777356EFD4444C4\",1)",
            "所需材料物品等": "对讲机、返工记录表",
            "步骤序号": "步骤5",
            "特别风险": "/",
            "特别风险管控": "/",
            "行号": 10,
            "阶段": "作业中"
        },
        {
            "作业事项任务": "填写报表",
            "作业标准2-图示(真实比例；拍摄时优选4:3模式)": "=DISPIMG(\"ID_249E30EE95FC49AC9777356EFD4444C4\",1)",
            "作业点": "深加工车间",
            "做到什么程度(数据定标)": "报表填写无误，现场已清理，钢球放置原位。",
            "具体做什么(动作分解)": "填写报表，清理现场。",
            "内容": "阶段:作业后；步骤序号:步骤6；作业点:深加工车间；作业事项任务:填写报表；所需材料物品等:深加工巡检记录表、护目镜、手套；具体做什么(动作分解):填写报表，清理现场。；做到什么程度(数据定标):报表填写无误，现场已清理，钢球放置原位。；特别风险:/；特别风险管控:/；作业标准2-图示(真实比例；拍摄时优选4:3模式):=DISPIMG(\"ID_249E30EE95FC49AC9777356EFD4444C4\",1)",
            "所需材料物品等": "深加工巡检记录表、护目镜、手套",
            "步骤序号": "步骤6",
            "特别风险": "/",
            "特别风险管控": "/",
            "行号": 11,
            "阶段": "作业后"
        }
    ]
    # 首先将方法进行拆分
    # for structured_row in structured_rows:
    total_essay_list = []
    total_filling_list = []
    index = 1
    start_time = time.time()  # 记录开始时间
    for structured_row in structured_rows:
        print(f"开始第{index}轮生成：")
        steps = extract_knowledge_point(structured_row, 5)
        print(f"完成知识点提取")
        # 排序归类
        essay_knowledge_point = []
        filling_knowledge_point = []
        for step in steps:
            if step['题型'] == '问答题':
                essay_knowledge_point.append(step)
            elif step['题型'] == '填空题':
                filling_knowledge_point.append(step)
        essay_list = build_essay_questions(essay_knowledge_point, structured_row['内容'])
        print(f"完成问答题生成")
        total_essay_list.extend(essay_list)
        filling_list = build_gap_filling_question(filling_knowledge_point, structured_row['内容'])
        print(f"完成填空题生成")
        total_filling_list.extend(filling_list)
        index += 1
    end_time = time.time()  # 记录结束时间
    total_minutes = (end_time - start_time) / 60
    print(f"[完成] 总共耗时约 {total_minutes:.2f} 分钟")
    print(total_essay_list)
    print(total_filling_list)


