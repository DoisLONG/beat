# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

import json
from typing import Optional
from fastapi import Form, HTTPException, FastAPI
import os
import uuid
import logging

from utils import check_and_create_directory, delete_directory, is_url
from routers import crawling

# Initialize logger
logger = logging.getLogger("crawlee_to_file")
logger.setLevel(os.getenv("LOGLEVEL", "INFO"))

upload_folder = "./uploaded_files/" # Directory for storing uploaded files
cache_folder = "./storage" # Cache directory

app = FastAPI()

@app.post("/v1/crawlee/crawling")
async def crawling_by_target_links(link_list: Optional[str] = Form(None)):
    """
    Processes the target link list, crawls web pages, and saves the content to local files.

    :param link_list: JSON string containing the list of URLs to crawl
    :return: Status message indicating whether data preparation was successful
    """

    link_list = json.loads(link_list) # Parse JSON string into a Python list
    if not isinstance(link_list, list):
        raise HTTPException(status_code=400, detail="link_list should be a list.")
    # check whether the link file already exists
    if not link_list:
        return {"status": 200, "message": "link_list is empty"}

    for link in link_list:
        try:
            if not is_url(link):
                logger.warning(f"[ upload ] link {link} is not a valid url")
                return {"status": 401, "message": f"link_list contains illegal URLs: {link}"}
        except Exception as e:
            logger.error(f"[ upload ] failed to validate link {link}: {e}")
            return {"status": 500, "message": f"Error validating link {link}: {str(e)}"}

    for link in link_list:
        try:
            encoded_link = link.replace("/", "%2F")
            save_path = upload_folder + encoded_link
            save_path_json = save_path + ".json"
            # Clear the cache directory to ensure fresh data is crawled
            await delete_directory(cache_folder)
            logger.info(f"[ upload ] processing link {link}")
            # Create the target storage directory (if not exists)
            await check_and_create_directory(save_path)
            # Call the crawling module to fetch data and save it locally
            await crawling([link], save_path_json, str(uuid.uuid4()))
        except Exception as e:
            logger.error(f"[ upload ] error processing link {link}: {e}")
            return {"status": 500, "message": f"Error processing link {link}: {e}"}
    return {"status": 200, "message": "Data preparation success"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=7010)