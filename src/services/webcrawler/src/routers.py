# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

import asyncio, aiohttp
import datetime
import json
import os
import re
import logging
from datetime import timedelta
from pathlib import Path
from typing import Dict, Any, List
from urllib.parse import urlparse
import threading
import dateutil.parser
import requests
from bs4.element import AttributeValueList
from crawlee import Glob, ConcurrencySettings, RequestOptions, RequestTransformAction
from crawlee.crawlers import (
    PlaywrightCrawler,
    PlaywrightCrawlingContext,
    PlaywrightPreNavCrawlingContext, )
from crawlee.sessions import SessionPool
from crawlee.storages import Dataset
from crawlee import Request

from robot_parser import GitHubAwareRobotParser

logger = logging.getLogger("crawler.routers")
logger.setLevel(os.getenv("LOGLEVEL", "INFO"))

CONFIG_PATH = Path(__file__).parent / "crawler_config.json"

unique_filter_lock = threading.Lock()  # add unique file lock
# global definition unique_file_set
unique_file_set = set()

asyn_unique_filter_lock = asyncio.Lock()

def load_config() -> Dict[str, Any]:
    """Load crawler configuration file"""
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)["crawler"]
    except FileNotFoundError:
        raise RuntimeError(f"Configuration file not found：{CONFIG_PATH}")
    except json.JSONDecodeError:
        raise RuntimeError("Configuration file format error")


config = load_config()

# Permitted URL suffixes
ALLOWED_EXTENSIONS = config.get("allowed_extensions", [])

# Regularly match URLs without suffixes
NO_EXTENSION_PATTERN = re.compile(config.get("no_extension_pattern", ""), re.IGNORECASE)


def is_redirect_page(url: str) -> bool:
    # Only match URLs that do not contain the ALLOWED_EXTENSIONS suffix
    return not re.search(r'(' + '|'.join(ALLOWED_EXTENSIONS) + r')$', url)

def transform_request(
        request_options: RequestOptions,
) -> RequestOptions | RequestTransformAction:
    """
        Process the request object to avoid duplicate crawling and adjust the request label based on the URL type.
        Parameters:
            request_options (RequestOptions):The request object containing the URL and other request parameters.
        Returns:
            RequestOptions | RequestTransformAction:
            - If the URL already exists in the unique set, return 'skip' to ignore the request.
            - Otherwise, return the modified `request_options` to proceed with the request.
    """
    url = request_options['url']
    with unique_filter_lock:
        # Use a global lock to ensure thread safety
        if url in unique_file_set:
            logger.debug(f'Skipping {url}   。because it is repetitive ...')
            return 'skip'
        # Sync set size {len(unique_file_set)}, adding URL: {url}
        unique_file_set.add(url)
    # Ensure all requests are enqueued
    request_options['always_enqueue'] = True
    # If it is a redirect page, label it as 'REDIRECT'
    if is_redirect_page(request_options['url']):
        request_options['label'] = 'REDIRECT'
    return request_options


def init_headers():
    """
         Initialize HTTP request headers to simulate a real browser visit and improve crawling success.
         Returns:
             dict:A dictionary containing common HTTP headers for web requests.
    """
    return {
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng, \
            */*;q=0.8,application/signed-exchange;v=b3;q=0.7",
        "Accept-Encoding": "gzip, deflate, br",
        "Accept-Language": "en-US,en;q=0.9,zh-CN;q=0.8,zh;q=0.7",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, \
            like Gecko) Chrome/113.0.0.0 Safari/537.36",
    }

# Function to get environment variable or default from config
def get_env_or_config(env_name, config_key, default=None):
    env_value = os.getenv(env_name)
    if env_value is not None and env_value != "":
        return env_value
    return config.get(config_key, default)

def init_filters() -> List[Glob]:
    """
       Initialize filters from the configuration file.
    """
    filters = get_env_or_config("CRAWL_FILTERS", "filters")
    return [Glob(e) for e in filters]


async def crawling(urls: list[str], output_path: str, dataset_id: str) -> None:
    """
        Asynchronous web crawling using Playwright, with support for concurrency control and session management.
        Parameters:
            urls (list[str]):List of URLs to be crawled.
            output_path (str):Path to save the crawled data.
            dataset_id (str):Dataset ID for managing the crawling task result.
    """
    # Retrieve crawling parameters from environment variables or configuration files
    max_concurrency = get_env_or_config("MAX_CONCURRENCY", "max_concurrency") # Maximum concurrent tasks
    max_tasks_per_minute = get_env_or_config("MAX_TASKS_PER_MINUTE", "max_tasks_per_minute") # Max tasks per minute
    max_retries = get_env_or_config("MAX_RETRIES", "max_retries") # Max retry attempts
    timeout_seconds = get_env_or_config("TIMEOUT_SECONDS", "timeout_seconds") # Timeout for each request
    max_requests = get_env_or_config("MAX_REQUESTS", "max_requests") # Max number of requests to crawl
    max_depth = get_env_or_config("MAX_DEPTH", "max_depth") # Max crawl depth
    session_pool_size = get_env_or_config("SESSION_POOL_SIZE", "session_pool_size") # Session pool size
    # Configure concurrency settings
    concurrency_settings = ConcurrencySettings(
        max_concurrency=int(max_concurrency),
        max_tasks_per_minute=int(max_tasks_per_minute),
    )
    # Initialize a session pool to manage browser sessions and improve efficiency
    session_pool = SessionPool(max_pool_size=int(session_pool_size))
    # Initialize Playwright crawler
    crawler = PlaywrightCrawler(
        browser_launch_options={"args": ["--no-sandbox", "--disable-setuid-sandbox"]},
        headless=True, # Run in headless mode for better performance
        browser_type="chromium", # Use Chromium as the browser backend
        max_request_retries=int(max_retries),
        request_handler_timeout=timedelta(seconds=int(timeout_seconds)),
        max_requests_per_crawl=int(max_requests),
        max_crawl_depth=int(max_depth),
        concurrency_settings=concurrency_settings,
        session_pool=session_pool
    )
    # Reset global unique_file_set
    global unique_file_set
    # Reset to a new set, ensuring that each crawl is a new set
    unique_file_set = set()
    # add first url to unique_file_set
    unique_file_set.add(urls[0])
    logger.info(f"init set quantity{len(unique_file_set)}")
    robots_cache = {}
    robots_cache_lock = asyncio.Lock()
    robots_cache_expiry = datetime.datetime.now() + timedelta(minutes=10)  # Set cache expiration time
    user_agent = init_headers()["User-Agent"]  # Ensure that user.agent is defined

    async def check_robots_permission(url: str) -> bool:
        """Check robots.txt permissions"""
        nonlocal robots_cache_expiry  # Key: Use nonlocal to allow internal functions to access external variables
        parsed = urlparse(url)
        domain = parsed.netloc
        logger.info(f"Checking robots.txt permission for URL: {url}")

        async with robots_cache_lock:
            # Check if the cache has expired
            if datetime.datetime.now() > robots_cache_expiry:
                logger.info("Robots cache expired, clearing cache.")
                robots_cache.clear()
                robots_cache_expiry = datetime.datetime.now() + timedelta(minutes=10)

            # Check if the robots.txt for this domain name has been cached
            if domain not in robots_cache:
                logger.info(f"No cached robots.txt for domain: {domain}, fetching now.")
                # Using GitHub Aware Robot Parser to parse robots.txt
                parser = GitHubAwareRobotParser()
                robots_url = f"{parsed.scheme}://{domain}/robots.txt"
                async with aiohttp.ClientSession() as session:
                    content = await fetch_robots_txt(session, robots_url)
                    if content:
                        # Using GitHubAwareRobotParser to parse content
                        parser.parse(content.splitlines())
                        robots_cache[domain] = parser
                        logger.info(f"Successfully parsed and cached robots.txt for domain: {domain}")
                    else:
                        logger.error(f"Failed to fetch robots.txt for domain: {domain}")
                        return True  # If robots.txt cannot be obtained, access is allowed by default

            parser = robots_cache.get(domain)
            if not parser:
                logger.warning(f"No parser available for domain: {domain}, allowing access by default.")
                return True

        # Check if you have permission to access the URL
        can_fetch = parser.can_fetch(user_agent, url)
        logger.info(f"Permission to fetch {url}: {'Allowed' if can_fetch else 'Denied'}")
        return can_fetch

    async def fetch_robots_txt(session, url: str) -> str:
        """Asynchronous retrieval of robots.txt content with retry"""
        logger.info(f"Fetching robots.txt from: {url}")
        for attempt in range(3):  # Try again up to 3 times
            try:
                async with session.get(url, headers=init_headers(), timeout=20) as response:
                    if response.status == 200:
                        content = await response.text()
                        logger.info(f"Successfully fetched robots.txt from: {url}")
                        return content
                    else:
                        logger.warning(f"Failed to fetch robots.txt from {url}: HTTP {response.status}")
            except Exception as ex:
                logger.warning(f"Attempt {attempt + 1} failed to fetch robots.txt from {url}: {ex}")
            await asyncio.sleep(2)  # Rest for 2 seconds and retry
        logger.error(f"All attempts failed to fetch robots.txt from: {url}")
        return ""  # Returning an empty string indicates failure

    @crawler.pre_navigation_hook
    async def log_navigation_url(context: PlaywrightPreNavCrawlingContext) -> None:
        logger.info(f'Navigating to {context.request.url} ...')
        # will set a timeout for all navigation methods
        context.page.set_default_navigation_timeout(600_000)
        # will set the page size before you go to the target URL
        await context.page.set_viewport_size({'width': 1280, 'height': 1024})

    @crawler.router.default_handler
    async def request_handler(context: PlaywrightCrawlingContext) -> None:
        """
            Handle crawler requests, checking robots.txt permissions and crawl depth before proceeding.
            Parameters:
                - context (PlaywrightCrawlingContext):The context object for the current crawling request.
        """
        url = context.request.url
        logger.info(f'Processing {url} ...') # URL Log the processing URL
        # Check robots.txt rules to determine if crawling is allowed
        if not await check_robots_permission(url):
            logger.info(f'Blocked by robots.txt: {url}')
        else:
            # Filtering logic
            depth = context.request.crawl_depth
            if depth <= max_depth:
                logger.info(f'The depth of {url} is:{depth}.')
                # Discover new links and enqueue them
                await context.enqueue_links(
                    # Only crawl links with the same hostname
                    strategy='same-hostname',
                    # URL Apply filtering conditions
                    include=init_filters(),
                    # Modify request before processing
                    transform_request_function=transform_request,
                )
                # Crawl page content
                data = await crawling_content(context=context)
                logger.debug(f"crawl data:{data}")
                # Push the crawled data to the dataset
                await context.push_data(data=data, dataset_name=dataset_id)

    @crawler.router.handler('REDIRECT')
    async def request_handler(context: PlaywrightCrawlingContext) -> None:
        """
            Handle requests with the 'REDIRECT' tag. This method only crawls links from redirect pages, without crawling page content.
            Parameters:
                - context (PlaywrightCrawlingContext):The context object for the current redirect request.

        """
        url = context.request.url
        logger.info(f'REDIRECT WEB is {context.request.url} ...')
        depth = context.request.crawl_depth
        if depth <= max_depth:
            if not await check_robots_permission(url):
                logger.info(f'Blocked by robots.txt: {url}')
                return
            logger.info(f'The depth of {context.request.url} is:{depth}.')
            await context.enqueue_links(
                strategy='same-hostname',
                include=init_filters(),
                transform_request_function=transform_request,
            )

    # Run the crawler with the initial list of requests.
    await crawler.run([Request.from_url(url, always_enqueue=True) for url in urls])
    try:
        # Attempt to open the specified dataset
        dataset = await Dataset.open(name=dataset_id)
    except Exception as e:
        logger.error(f"Failed to open {dataset_id}: , because {e}")
        return
    # Get data from the dataset
    page = await dataset.get_data()
    if page.count > 0:
        # If the dataset contains data, export it to JSON format
        await crawler.export_data_json(output_path, dataset_name=dataset_id)


async def crawling_content(context: PlaywrightCrawlingContext):
    """
        Crawl the specified content under the current URL.
    Args:
        context: current crawling web page
    Returns:
        dict
    """
    await context.page.wait_for_load_state('domcontentloaded')

    title_locator = await context.page.query_selector('title')
    title = None
    if title_locator:
        title = await title_locator.text_content()
        if title:
            logger.info(f'The title of {context.request.url} is:{title}.')
    filename = context.request.url.replace('/', '%2F')
    # Extract data from the page.
    data = {
        'filename': filename,
        'source_url': context.request.url,
        'title': title,
        'crawl_time': datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%d %H:%M:%S'),
        "origin_url": ""
    }
    publish_time = None
    if context.request.url.endswith('.md'):
        # Locate the main text area (GitHub MD document specific selector)
        main_content, publish_time, title = await extract_and_clean_content(context,
                                                                            ['article'])
    elif context.request.url.endswith('.html') or context.request.url.endswith('.htm'):
        # Processing. html/. html files
        main_content, publish_time, title = await extract_and_clean_content(context, ['article', 'main'])
    elif context.request.url.endswith('.ipynb'):
        # Processing. ipynb files
        raw_url = context.request.url.replace("github.com", "raw.githubusercontent.com").replace("/blob/", "/")
        # Analyze warehouse information
        match = re.match(r"https://raw.githubusercontent.com/([^/]+)/([^/]+)/([^/]+)/(.*)", raw_url)
        if match:
            owner, repo, branch, file_path = match.groups()
            api_url = f"https://api.github.com/repos/{owner}/{repo}/commits?path={file_path}&per_page=1"
            response = requests.get(api_url, headers=init_headers())
            if response.status_code == 200:
                commit_data = response.json()
                if commit_data:
                    publish_time = commit_data[0]["commit"]["committer"]["date"]
                else:
                    publish_time = None
            else:
                publish_time = None
        response = requests.get(raw_url)
        if response.status_code == 200:
            ipynb_data = response.json()
            extracted_texts = []
            ipynb_title = None
            for cell in ipynb_data.get("cells", []):
                if cell["cell_type"] == "markdown":
                    # Extract the first title
                    if ipynb_title is None:
                        title_lines = [line.strip() for line in cell["source"] if line.strip().startswith("# ")]
                        if title_lines:
                            ipynb_title = title_lines[0][2:].strip()
                            logger.info(f'Extracted title from .ipynb: {ipynb_title}')

                    extracted_texts.append("\n".join(cell["source"]))
                elif cell["cell_type"] == "code":
                    extracted_texts.append("\n".join(cell["source"]))  # Extract code
            main_content = "\n".join(extracted_texts)
            if ipynb_title:
                title = ipynb_title
        else:
            main_content = ''
            logger.error(f"Failed to fetch notebook content from {raw_url}. Status code: {response.status_code}")
    else:
        # Backup selector: attempt to locate the general body area
        main_content, publish_time, title = await extract_and_clean_content(context,
                                                                            ['main', '.main-content', '#content',
                                                                             'article'])

    if main_content:
        data['content'] = main_content
    else:
        data['content'] = ""
    if publish_time:
        dt = parse_publish_time(publish_time)
        data['publish_time'] = dt.strftime('%Y-%m-%d %H:%M:%S')
    else:
        data['publish_time'] = ""
    if title:
        data['title'] = title

    # print("-----s%", data)
    # Push the extracted data to the default dataset.
    return data


def parse_publish_time(publish_time):
    try:
        dt = dateutil.parser.parse(publish_time)
        return dt
    except (ValueError, TypeError) as e:
        logger.error(f"Error parsing publish_time: {e}")
        return None


async def extract_and_clean_content(context: PlaywrightCrawlingContext, selectors: List[str]) -> tuple[
    str, str | AttributeValueList | None, str]:
    """
    Locate the body area based on the incoming CSS selector list and clean up interfering elements
    """
    main_content_text = ""
    main_content_locator = None
    publish_time = None
    title = None
    for selector in selectors:
        main_content_locator = await context.page.query_selector(selector)
        if main_content_locator:
            main_content_text = await main_content_locator.text_content()
            title_selector = await main_content_locator.query_selector("h1")
            if title_selector:
                title = await title_selector.text_content()
            break

    # Find all <relative-time> tags
    relative_times = await context.page.query_selector_all("relative-time")
    if relative_times:
        publish_time = await relative_times[0].get_attribute("datetime")  # Take the first one (latest)

    if not main_content_locator:
        logger.warning("Body area not found, use the entire page text as content")
        main_content_text = await context.page.text_content("body")
        main_content_text = main_content_text.replace("\n", " ")
    return main_content_text, publish_time, title

# if __name__ == '__main__':
#     # encoded_link = "https://github.com/openvinotoolkit/openvino_notebooks/blob/latest/notebooks/distil-whisper-asr/README.md"
#     encoded_link = "https://github.com/openvinotoolkit/openvino_notebooks/blob/latest/notebooks/sdxl-turbo/sdxl-turbo.ipynb"
#     link_path = encoded_link.replace("/", "%2F")
#     upload_folder = "./uploaded_files/"
#     output_path = upload_folder + link_path + ".json"
#     asyncio.run(crawling(urls=[encoded_link], output_path=output_path, unique_filter=[]))
