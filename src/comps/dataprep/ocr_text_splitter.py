# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

from typing import List, Optional, Any
import re
import logging
from concurrent.futures import ThreadPoolExecutor

logger = logging.getLogger(__name__)

class OCRTextSplitter():
    # Class-level constants
    NAVIGATION_PATTERNS = {
        "back to top ⬆",
        # Add other navigation link patterns here
    }

    def __init__(
        self,
        chunk_size: int = 1000,
        chunk_overlap: int = 100,
        separator: str = " ",
        is_separator_regex: bool = False,
        strip_whitespace: bool = True,
        **kwargs: Any,
    ) -> None:
        """Create a new TextSplitter."""
        self._separator = separator
        self._is_separator_regex = is_separator_regex
        self._chunk_size = chunk_size
        self._chunk_overlap = chunk_overlap
        self._strip_whitespace = strip_whitespace

    def _join_docs(self, docs: List[str], separator: str) -> Optional[str]:
        """Join documents with the separator."""
        text = separator.join(docs).strip() if self._strip_whitespace else separator.join(docs)
        return text if text else None
        
    def _split_text_with_separator(self, text: str, separator: str) -> List[str]:
        """Splits the text by the given separator."""
        if separator:
            return [s for s in re.split(separator, text) if s]
        return list(text)  # Split by individual characters if no separator

    def _get_metadata_key(self, rect):
        """Create metadata key using rect list information"""
        return (rect[0], rect[1], rect[2], rect[3])

    def _create_chunk_with_metadata(self, text_list: List[str], metadata: dict, separator: str) -> Optional[dict]:
        """Create a chunk with text and metadata."""
        if not text_list:
            return None

        text = self._join_docs(text_list, separator)
        if not text:
            return None

        # Get page info directly from metadata
        page_info = metadata["page"]

        # Extract all rects from metadata["zone"]
        zone_rects = [item["rect"] for item in metadata["zone"] if "rect" in item]
        if not zone_rects:
            return None

        # Extract all rects from metadata["rects"]
        metadata_rects = metadata["rects"]
        if not metadata_rects:
            return None

        # Calculate merged_rect
        min_x1 = min(rect[0] for rect in zone_rects)  # Zone rect's minimum x1
        min_y1 = min(rect[1] for rect in zone_rects)  # Zone rect's minimum y1
        max_x2 = max(rect[2] for rect in zone_rects)  # Zone rect's maximum x2
        max_y2 = max(rect[3] for rect in metadata_rects)  # Metadata rect's maximum y2

        merged_rect = {
            "x1": min_x1,
            "y1": min_y1,
            "x2": max_x2,
            "y2": max_y2
        }

        return {
            "text": text,
            "metadata": {
                "page": page_info,
                "rect": merged_rect
            }
        }


    def _split_ocr_text_with_metadata(self, ocr_texts: List[dict]) -> List[dict]:
        """Split OCR text respecting both hierarchical and flat title structures."""
        def create_new_chunk():
            return {
                "text": [],
                "metadata": {
                    "page": None,
                    "zone": [],
                    "rects": []
                },
                "tracked_rects": set(),
                "current_section": {
                    "level": None,
                    "parent": None
                }
            }

        def get_title_info(text: str) -> dict:
            """Analyze title text to determine if it's hierarchical or flat."""
            if not text:
                return {"is_hierarchical": False, "level": None, "number": None}

            # Try to match hierarchical patterns like "1.", "1.1", "1.2.3"
            # Modified pattern to make the text part optional
            match = re.match(r'^(\d+(?:\.\d+)*)\s*[\.|\s]?(.*)$', text.strip())
            if match:
                numbers = tuple(int(x) for x in match.group(1).split('.'))
                return {
                    "is_hierarchical": True,
                    "level": numbers,
                    "number": match.group(1),
                    "text": match.group(2)
                }

            return {
                "is_hierarchical": False,
                "level": None,
                "number": None,
                "text": text
            }

        chunks = []
        current_chunk = create_new_chunk()
        current_length = 0
        separator = self._separator
        separator_len = len(separator)

        max_line_length = 0
        lines_to_check = 5  # Check first 5 lines
        lines_checked = 0

        for ocr_text in ocr_texts:
            for segment in ocr_text["segments"]:
                line_length = len(segment["text"])
                max_line_length = max(max_line_length, line_length)
                lines_checked += 1
                if lines_checked >= lines_to_check:
                    break
            if lines_checked >= lines_to_check:
                break

        min_chunk_length = max_line_length if max_line_length > 0 else self._chunk_overlap

        for i, ocr_text in enumerate(ocr_texts):
            current_is_title = ocr_text["zone"]["type"] == "title"
            current_page = ocr_text["page"]["page_num"]

            # Handle page changes
            if current_chunk["metadata"]["page"] and current_chunk["metadata"]["page"]["page_num"] != current_page:
                if current_chunk["text"]:
                    chunk = self._create_chunk_with_metadata(
                        current_chunk["text"],
                        current_chunk["metadata"],
                        separator
                    )
                    if chunk:
                        chunks.append(chunk)
                current_chunk = create_new_chunk()
                current_length = 0

            if not current_chunk["metadata"]["page"]:
                current_chunk["metadata"]["page"] = ocr_text["page"]

            # Handle titles
            if current_is_title:
                title_text = ocr_text["segments"][0]["text"] if ocr_text["segments"] else ""
                title_info = get_title_info(title_text)

                # Determine if we should start a new chunk based on:
                # 1. Minimum content length requirement
                # 2. Title type (hierarchical or non-hierarchical)
                should_start_new_chunk = (
                    current_chunk["text"] and  # Has content
                    current_length >= min_chunk_length and  # Content is long enough
                    (
                        # For hierarchical titles: only split on top-level titles
                        (title_info["is_hierarchical"] and
                         current_chunk["current_section"]["level"] is not None and
                         title_info["level"] is not None and
                         len(title_info["level"]) == 1) or  # Top-level hierarchical title
                        (not title_info["is_hierarchical"])  # Non-hierarchical title
                    )
                )
                
                if should_start_new_chunk:
                    chunk = self._create_chunk_with_metadata(
                        current_chunk["text"],
                        current_chunk["metadata"],
                        separator
                    )
                    if chunk:
                        chunks.append(chunk)
                    current_chunk = create_new_chunk()
                    current_length = 0

                # Update current section info
                current_chunk["current_section"]["level"] = (
                    title_info["level"] if title_info["is_hierarchical"] else None
                )

            # Process segments
            for segment in ocr_text["segments"]:
                text = segment["text"]
                rect = segment["rect"]
                rect_key = self._get_metadata_key(rect)

                splits = self._split_text_with_separator(text, separator)
                for idx, split in enumerate(splits):
                    word_len = len(split)

                    if current_length + word_len + (separator_len if current_chunk["text"] else 0) > self._chunk_size:
                        if idx > 0:
                            zone_rect = ocr_text["zone"].get("rect")
                            if zone_rect and self._get_metadata_key(zone_rect) not in current_chunk["tracked_rects"]:
                                current_chunk["metadata"]["zone"].append(ocr_text["zone"])
                                current_chunk["tracked_rects"].add(self._get_metadata_key(zone_rect))

                        if current_length > self._chunk_size:
                            logger.warning(
                                f"Created a chunk of size {current_length}, "
                                f"which is longer than the specified {self._chunk_size}"
                            )

                        chunk = self._create_chunk_with_metadata(
                            current_chunk["text"],
                            current_chunk["metadata"],
                            separator
                        )
                        if chunk:
                            chunks.append(chunk)

                        # Handle chunk overlap
                        # Keep popping from the start until we have appropriate overlap
                        overlap_length = current_length
                        overlap_texts = current_chunk["text"].copy()

                        while (overlap_length > self._chunk_overlap or
                               (overlap_length + word_len + (separator_len if overlap_texts else 0) > self._chunk_size
                                and overlap_length > 0)):
                            if overlap_texts:
                                first_text = overlap_texts.pop(0)
                                overlap_length -= len(first_text) + (separator_len if len(overlap_texts) > 0 else 0)

                        # Initialize new chunk with overlap text but fresh metadata
                        current_chunk = {
                            "text": overlap_texts,
                            "metadata": {
                                "page": ocr_text["page"],
                                "zone": [],
                                "rects": []
                            },
                            "tracked_rects": set(),
                            "current_section": {
                                "level": current_chunk.get("current_section", {}).get("level"),
                                "parent": current_chunk.get("current_section", {}).get("parent")
                            }
                        }
                        current_length = overlap_length

                    current_chunk["text"].append(split)
                    if rect_key not in current_chunk["tracked_rects"]:
                        current_chunk["metadata"]["rects"].append(rect)
                        current_chunk["tracked_rects"].add(rect_key)
                    current_length += word_len + (separator_len if len(current_chunk["text"]) > 1 else 0)

            # Handle zone rect
            zone_rect = ocr_text["zone"].get("rect")
            if zone_rect and self._get_metadata_key(zone_rect) not in current_chunk["tracked_rects"]:
                current_chunk["metadata"]["zone"].append(ocr_text["zone"])
                current_chunk["tracked_rects"].add(self._get_metadata_key(zone_rect))

        # Handle final chunk
        if current_chunk["text"]:
            final_chunk = self._create_chunk_with_metadata(
                current_chunk["text"],
                current_chunk["metadata"],
                separator
            )
            if final_chunk:
                chunks.append(final_chunk)

        return chunks

    def _process_zone_lines(self, zone: dict, page_info: dict) -> Optional[dict]:
        """Process lines in a zone and calculate total text length."""
        if zone["type"] not in ["text", "title", "list", "index"] or not zone.get("lines"):
            return None

        # Skip navigation elements (typically single-line titles with specific patterns)
        if (zone["type"] == "title" and
            len(zone["lines"]) == 1 and
            zone["lines"][0].get("text", "").lower().strip() in self.NAVIGATION_PATTERNS):
            return None

        zone_segments = []
        total_text_length = 0

        for line in zone["lines"]:
            if line.get("text"):
                zone_segments.append({
                    "text": line["text"],
                    "rect": line["rect"]
                })
                total_text_length += len(line["text"])

        if not zone_segments:
            return None

        return {
            "segments": zone_segments,
            "page": page_info,
            "total_length": total_text_length
        }

    def _process_single_page(self, page: dict) -> List[dict]:
        """Process a single page and return its OCR texts."""
        page_zones = []
        page_info = {
            "page_num": page["page_info"]["page_no"],
            "width": page["page_info"]["page_size"]["width"],
            "height": page["page_info"]["page_size"]["height"]
        }
        
        for zone in page["zones"]:
            processed_zone = self._process_zone_lines(zone, page_info)
            if processed_zone:
                ocr_text = {
                    "segments": processed_zone["segments"],
                    "page": processed_zone["page"],
                    "zone": {
                        "type": zone["type"],
                        "rect": zone["rect"]
                    },
                    "total_length": processed_zone["total_length"]
                }
                page_zones.append(ocr_text)
        return page_zones

    def split_text(self, pages_info: List[dict]) -> List[dict]:
        """
        Split the input OCR texts (with metadata) into chunks.
        
        Args:
            pages_info: List of dictionaries containing OCR text data with metadata
            
        Returns:
            List of dictionaries containing chunked text with associated metadata
        """
        if not pages_info:
            logger.warning("Received empty or None pages_info")
            return []
            
        all_zones = []
        
        with ThreadPoolExecutor() as executor:
            future_to_page = {executor.submit(self._process_single_page, page): page 
                            for page in pages_info}
            
            for future in future_to_page:
                try:
                    page_zones = future.result()
                    all_zones.extend(page_zones)
                except Exception as e:
                    logger.error(f"Error processing page: {e}")
        
        chunks = self._split_ocr_text_with_metadata(all_zones)

        for i, chunk in enumerate(chunks):
            print(f"\nChunk {i + 1}:")
            print(f"Text: {chunk['text']}")
            print(f"Page: {chunk['metadata']['page']}")
            print(f"Rect: {chunk['metadata']['rect']}")
            
        return chunks
