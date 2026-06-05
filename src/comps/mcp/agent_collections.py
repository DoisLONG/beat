# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

import json
import re
from typing import List, Union

from openai import OpenAI
from comps import FakeTextContent, FakeToolContent, ToolCallResult, UserQuery
from template import prompt, generate_prompt, generate_param_prompt


def extract_json_from_response(text):
    # 移除 <think>...</think> 内容
    text = re.sub(r'<think>[\s\S]*?</think>', '', text)
    # 优先提取 ```json ... ``` 中的内容
    match = re.search(r'```json\s*([\s\S]*?)\s*```', text)
    if match is None:
        match = re.search(r'(\[.*\])', text, re.DOTALL)
    json_str = match.group(1) if match else text
    try:
        return json.loads(json_str)
    except json.JSONDecodeError as e:
        raise ValueError(f"JSON 解析失败: {e}")

class ModelAdapter:
    def __init__(self, model_name: str, api_key: str, base_url: str):
        self.generate_prompt = generate_prompt
        self.client = OpenAI(
            api_key=api_key,
            base_url=base_url,
        )
        self.model_name = model_name
        self.system_prompt = prompt
        self.generate_param_prompt = generate_param_prompt

    def create(self, messages: list, history: list, tools: list):
        """
        将 messages 与 tools 信息封装后调用模型，并返回一个 FakeResponse 对象。
        """
        # 针对简单实现，这里只取最后一条消息内容作为用户输入
        user_message = messages
        # 拼接工具信息（注意实际情况可能需要更灵活的处理）
        combined_input = f"{json.dumps(tools)}\n那么我的问题是:{user_message}"

        # 调用模型的聊天接口，使用流式输出
        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": combined_input}
        ]
        chat_params = {
            "model": self.model_name,
            "messages": messages,
        }
        chat_completion = self.client.chat.completions.create(**chat_params)
        response_text = chat_completion.choices[0].message.content
        print("model (full response):", response_text)
        # 尝试解析 JSON，如果解析失败，就直接使用原文本
        result = None
        try:
            parsed_result = extract_json_from_response(response_text)
            print(parsed_result)
            if isinstance(parsed_result, dict):
                type = parsed_result['type']
                if type == 'no_tool':
                    call_info = FakeTextContent(text=parsed_result['text'], type=type)
                else:
                    call_info = FakeToolContent(type=type, name=parsed_result['name'], input=parsed_result['input'])
                result = ToolCallResult(type=type, result=call_info)
            else:
                call_info = []
                for item in parsed_result:
                    call_info.append(FakeToolContent(type=item['type'], name=item['name'], input=item['input']))
                result = ToolCallResult(type="chain", result=call_info)
        except Exception:
            print("转化出错")
        return result

    # def generate_context(self, generate_info: UserQuery, history: List):
    #
    #     response_text = chat_completion.choices[0].message.content
    #     print("model (full response):", response_text)
    #     call_info = FakeTextContent(text=response_text, type="text")
    #     return ToolCallResult(type="text", result=call_info)

    def generate_param_by_current_node(self,
                                       chain_history: List[dict],
                                       current_node_info: dict,
                                       user_input: str,
                                       history: List):
        # 组建输入
        input_template = {
            "user_input": user_input,
            "chain_history": chain_history,
            "current_node_info": current_node_info,
        }
        messages = [
            {"role": "system", "content": self.generate_param_prompt},
            {"role": "user", "content": json.dumps(input_template)}
        ]
        chat_params = {
            "model": self.model_name,
            "messages": messages,
        }
        chat_completion = self.client.chat.completions.create(**chat_params)
        response_text = chat_completion.choices[0].message.content
        print("model (full response):", response_text)
        return extract_json_from_response(response_text)
