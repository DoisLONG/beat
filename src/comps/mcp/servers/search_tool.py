# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

from mcp.server import FastMCP
import httpx
import os

# Initialize FastMCP server
mcp = FastMCP("Search")

WEBSEARCH_API_URL = os.getenv("WEBSEARCH_API_URL","http://localhost:7050/v1/web_search")

@mcp.tool(name="web_search")
async def web_search(query: str, count: int = 5) -> str:
    """
    Use multi engine web search services to obtain relevant information summaries.

    Args:
        query(str): user input
        count(int): Return the number of results

    Returns:
        Search Summary List (excluding metadata)
    """
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                WEBSEARCH_API_URL,  # Your web_dearch service address
                json={"text": query,"count":count},
                timeout=10
            )
            response.raise_for_status()
            data = response.json()
            return "".join([item.get("text", "") for item in data['retrieved_docs']])
    except Exception as e:
        return f"Search service call failed:{str(e)}"

if __name__ == "__main__":
    # Initialize and run the server
    mcp.run(transport='stdio')



