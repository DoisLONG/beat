# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

import json
import os
import re
from typing import Optional, List
from contextlib import AsyncExitStack

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from dotenv import load_dotenv
from comps.cores.mega.logger import CustomLogger
from comps import register_microservice, ServiceType, opea_microservices, TextDoc, ToolResultItem, UserQuery, \
    ToolResult, McpDoc

from comps.mcp.agent_collections import ModelAdapter
from comps.mcp.template import generate_prompt

# --- Environment Setup ---
# Load environment variables for model configuration and credentials
api_key = os.environ["MODEL_API_KEY"]
base_url = os.environ["MODEL_BASE_URL"]
model_name = os.environ["MODEL_NAME"]
tool_path = "./servers/tool_config.json"
# History of prior exchanges, shared across calls
message_history = []

logger = CustomLogger("mcp-client")
logflag = os.getenv("LOGFLAG", False)


class MCPClient:
    """
    Orchestrates connections to multiple MCP tool subprocesses,
    delegates user queries to either the language model or tool calls,
    and aggregates tool outputs for final responses.
    """
    def __init__(self):
        # Initialize session and client objects
        self.exit_stack = AsyncExitStack()
        # Adapter instance to route messages through the specified model
        self.model_adapter = ModelAdapter(model_name=model_name, api_key=api_key, base_url=base_url)
        self.stdio_pairs = []
        # Holds active ClientSession objects for each tool server
        self.sessions: List[Optional[ClientSession]] = []

    # --- Connection Management ---
    async def connect_to_server(self, server_script_paths: List[str]):
        """
          For each script path in server_script_paths:
          1. Determine interpreter (Python or Node)
          2. Launch stdio client subprocess
          3. Initialize and store a ClientSession
          """
        python_exec = os.getenv("PYTHON_EXECUTABLE", "python")
        env = os.environ.copy()
        for path in server_script_paths:
            command = python_exec if path.endswith(".py") else "node"
            server_params = StdioServerParameters(command=command, args=[path], env=env)
            # Enter stub client and session contexts
            stdio_pair = await self.exit_stack.enter_async_context(stdio_client(server_params))
            self.stdio_pairs.append(stdio_pair)
            # Perform handshake or initialization protocol
            session = await self.exit_stack.enter_async_context(ClientSession(*stdio_pair))
            await session.initialize()
            self.sessions.append(session)
        if logflag:
            logger.info(f"✅ Connected to {len(self.sessions)} tool services")

    async def call_tool_by_name(self, tool_name: str, tool_args: dict):
        """
               Searches all connected sessions for a tool matching tool_name,
               invokes it with tool_args, and returns the result.

               Raises ValueError if no matching tool is found.
               """
        for session in self.sessions:
            response = await session.list_tools()
            for tool in response.tools:
                if tool.name == tool_name:
                    if logflag:
                        logger.info(f"🔧 Invoking {tool_name} with args: {tool_args}")
                    return await session.call_tool(tool_name, tool_args)
        raise ValueError(f"Tool '{tool_name}' not found among sessions.")

    async def process_query(self, query: str, tool_infos: List) -> ToolResult:
        """
        Main entry for handling a user query.
        1. Gather tool metadata.
        2. Ask model whether to use a tool, chain tools, or answer directly.
        3a. If "no_tool": wrap direct text response.
        3b. If "tool": call a single tool and return its output.
        3c. If "chain": execute sequential tool steps, collect history, then return.
        """
        # Compile metadata for available tools
        messages = [
            {
                "role": "user",
                "content": query
            }
        ]
        responses = [await session.list_tools() for session in self.sessions]
        available_tools = [
            {
                "name": tool.name,
                "description": tool.description,
                "input_schema": tool.inputSchema
            }
            for response in responses
            for tool in response.tools
        ]
        # Ask the model for dispatch instructions
        response = self.model_adapter.create(
            messages=messages,
            history=message_history,
            tools=available_tools
        )
        logger.info(response)
        while True:
            type = response.type
            # Handle simple text reply
            if type == "no_tool":
                return ToolResult(type=type, generate_info=UserQuery().dict(), query=query, prompt=generate_prompt,
                                  tool_infos=tool_infos)
            elif type == "tool":
                # Handle single tool call
                tool_name, tool_params = response.result.name, response.result.input
                # Execute tool call
                result = await self.call_tool_by_name(tool_name, tool_params)
                if logflag:
                    logger.info(f"{tool_name}`s result ：{[texts.text for texts in result.content]}")
                tool_chain = [response.result.name]
                tool_result = ToolResultItem(name=response.result.name,
                                             result="\n".join([texts.text for texts in result.content]))
                generate_info = UserQuery(user_input=query, tool_chain=tool_chain, tool_result=[tool_result])
                return ToolResult(type=type, generate_info=generate_info.model_dump(), query=query,
                                  prompt=generate_prompt, tool_infos=tool_infos)
            elif type == "chain":
                # Handle tool chains
                chain_full = response.result
                chain_history = []
                tool_chain = []
                tool_result = []
                for tool in chain_full:
                    current_tool_name = tool.name
                    tool_chain.append(current_tool_name)
                    current_node_info = next((tool for tool in available_tools if tool["name"] == current_tool_name),
                                             None)
                    response = self.model_adapter.generate_param_by_current_node(
                        current_node_info=current_node_info,
                        chain_history=chain_history,
                        user_input=query,
                        history=message_history
                    )
                    current_tool_input = response
                    # Execute tool call
                    result = await self.call_tool_by_name(current_tool_name, current_tool_input)
                    if logflag:
                        logger.info(f"{current_tool_name}`s result ：{[texts.text for texts in result.content]}")
                    chain_history.append(
                        {
                            "name": current_tool_name,
                            "result": [texts.text for texts in result.content]
                        }
                    )
                    tool_result.append(ToolResultItem(name=current_tool_name,
                                                      result=[texts.text for texts in result.content].__str__()))
                generate_info = UserQuery(user_input=query, tool_chain=tool_chain, tool_result=tool_result)
                return ToolResult(type=type, generate_info=generate_info.model_dump(), query=query,
                                  prompt=generate_prompt, tool_infos=tool_infos)
            else:
                if logflag:
                    logger.info("Tool invocation error........")
                return ToolResult(type=type, generate_info=UserQuery().dict(), query=query, prompt=generate_prompt,
                                  tool_infos=tool_infos)

    async def cleanup(self):
        """Clean up resources"""
        await self.exit_stack.aclose()


# --- Utility Function: Load Tool Configuration ---
# Reads the JSON config at 'tool_path' for available microservice definitions
def get_mcp_tool_config(tool_file_path: str):
    if not os.path.exists(tool_file_path):
        raise FileNotFoundError(f"Tool file {tool_file_path} does not exist.")
    with open(tool_file_path, 'r') as file:
        try:
            tool_config = json.load(file)
        except json.JSONDecodeError as e:
            raise ValueError(f"Failed to decode JSON from {tool_file_path}: {e}")
    return tool_config


re_userinput = re.compile('user: (.*)\nassistant:')


def try_to_load_json(s):
    """
    Attempt to parse a string as JSON.
    :param s: The string to check.
    :return: The parsed JSON object if valid, otherwise None.
    """
    try:
        return json.loads(s)
    except json.JSONDecodeError:
        return None


def parse_input_text(input_text: str):
    """
    parse input text to extract the question part
    :param input_text: The input text to parse.
    :return: The question part of the input text.
    """

    last_content = ""
    # input text will be json
    if parsed_json := try_to_load_json(input_text):
        if len(parsed_json) >= 1:
            last_content = parsed_json[-1].get("content", "")
    # input text will be: 'text': 'user: what is deep learning\nassistant: i am fine😊\n'
    elif (match := re_userinput.match(input_text)) and match.group(1):
        last_content = match.group(1).strip()
    else:
        last_content = input_text.strip()

    # filter out <think>*</think>
    filtered_last_content = re.sub(r'<think>\\n.*?\\n</think>\\n\\n', '', last_content, flags=re.DOTALL)
    return filtered_last_content


# --- Microservice Registration: Query Endpoint ---
@register_microservice(
    name="opea_service@mcp_client",
    service_type=ServiceType.MCP,
    endpoint="/v1/mcp",
    host="0.0.0.0",
    port=9999,
)
async def mcp_choice_function(
        input: McpDoc
):
    """
    Handles incoming MCP queries by:
    1. Loading tool configs
    2. Connecting to each specified tool service
    3. Delegating query processing
    4. Cleaning up sessions
    """
    if logflag:
        logger.info(input.__str__())
    text = parse_input_text(input.text)
    if logflag:
        logger.info(f"user query:{text}")
    tool_config = get_mcp_tool_config(tool_path)
    tool_paths = input.mcp_list
    tool_simple_infos = [{"tool_name": tool["tool_name"], "flag": tool["flag"]} for tool in tool_config]
    client = MCPClient()
    try:
        await client.connect_to_server(tool_paths)
        response = await client.process_query(text, tool_simple_infos)
        print(response)
        # await client.connect_to_server("D:\\local\\pycharm\\mcp_demo\\server\\echo_server.py")
    finally:
        await client.cleanup()
    return response


@register_microservice(
    name="opea_service@mcp_client",
    service_type=ServiceType.MCP,
    endpoint="/v1/mcp/infos",
    host="0.0.0.0",
    port=9999
)
async def get_mcp_infos():
    """
    Provides metadata on all MCP tools without activating them.
    """
    tool_config = get_mcp_tool_config(tool_path)
    result = [
        {
            "tool_name": tool["tool_name"],
            "tool_path": tool["tool_path"],
            "flag": tool["flag"],
            "enabled": False
        }
        for tool in tool_config
    ]
    return result


if __name__ == "__main__":
    opea_microservices["opea_service@mcp_client"].start()
