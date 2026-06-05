# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

import sys
import os

current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
sys.path.append(project_root)

from ocr_text_splitter import OCRTextSplitter

import unittest
from typing import List, Dict, Optional, Any
import re

class TestOCRTextSplitter(unittest.TestCase):
    def setUp(self):
        self.splitter = OCRTextSplitter(chunk_size=1000, chunk_overlap=100)

    def test_split_ocr_text_with_metadata_single_chunk(self):
        """Test splitting OCR text into a single chunk."""
        pages_info = [
            {
                "page_info": {
                    "page_no": 1,
                    "page_size": {
                        "width": 100,
                        "height": 100
                    }
                },
                "zones": [
                    {
                        "type": "text",
                        "rect": [0, 0, 10, 10],
                        "is_discard": False,
                        "lines": [
                            {
                                "text": "This is a test",
                                "rect": [0, 0, 10, 10],
                                "type": "text",
                                "is_discard": False
                            }
                        ]
                    }
                ]
            }
        ]
        result = self.splitter.split_text(pages_info)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["text"], "This is a test")
        metadata = result[0]["metadata"]
        self.assertEqual(metadata["page"]["page_num"], 1)
        self.assertEqual(metadata["rect"], {"x1": 0, "y1": 0, "x2": 10, "y2": 10})

    def test_split_ocr_text_with_metadata_multiple_chunks(self):
        """Test splitting OCR text into multiple chunks based on chunk_size."""
        self.splitter = OCRTextSplitter(chunk_size=10, chunk_overlap=2)
        pages_info = [
            {
                "page_info": {
                    "page_no": 1,
                    "page_size": {
                        "width": 100,
                        "height": 100
                    }
                },
                "zones": [
                    {
                        "type": "text",
                        "rect": [0, 0, 10, 10],
                        "is_discard": False,
                        "lines": [
                            {
                                "text": "This is a long test text that should be split",
                                "rect": [0, 0, 10, 10],
                                "type": "text",
                                "is_discard": False
                            }
                        ]
                    }
                ]
            }
        ]
        result = self.splitter.split_text(pages_info)
        self.assertTrue(len(result) > 1)
        self.assertTrue(all("text" in chunk for chunk in result))
        self.assertTrue(all("metadata" in chunk for chunk in result))

    def test_position_metadata(self):
        """Test the Position Metadata handling in splitting OCR text."""
        pages_info = [
            {
                "page_info": {
                    "page_no": 1,
                    "page_size": {
                        "width": 100,
                        "height": 100
                    }
                },
                "zones": [
                    {
                        "type": "text",
                        "rect": [0, 0, 10, 10],
                        "is_discard": False,
                        "lines": [
                            {
                                "text": "First text",
                                "rect": [0, 0, 10, 10],
                                "type": "text",
                                "is_discard": False
                            }
                        ]
                    }
                ]
            }
        ]
        result = self.splitter.split_text(pages_info)
        self.assertTrue(len(result) > 0)
        self.assertTrue(all(isinstance(chunk["metadata"], dict) for chunk in result))
        metadata = result[0]["metadata"]
        self.assertEqual(metadata["rect"], {"x1": 0, "y1": 0, "x2": 10, "y2": 10})

    def test_empty_input(self):
        """Test handling of empty input."""
        result = self.splitter.split_text([])
        self.assertEqual(result, [])

    def test_single_word(self):
        """Test handling of single word input."""
        pages_info = [
            {
                "page_info": {
                    "page_no": 1,
                    "page_size": {
                        "width": 100,
                        "height": 100
                    }
                },
                "zones": [
                    {
                        "type": "text",
                        "rect": [0, 0, 10, 10],
                        "is_discard": False,
                        "lines": [
                            {
                                "text": "Test",
                                "rect": [0, 0, 10, 10],
                                "type": "text",
                                "is_discard": False
                            }
                        ]
                    }
                ]
            }
        ]
        result = self.splitter.split_text(pages_info)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["text"], "Test")

    def test_chunking_with_overlap(self):
        """Test chunking with overlap."""
        self.splitter = OCRTextSplitter(chunk_size=10, chunk_overlap=5)
        pages_info = [
            {
                "page_info": {
                    "page_no": 1,
                    "page_size": {
                        "width": 100,
                        "height": 100
                    }
                },
                "zones": [
                    {
                        "type": "text",
                        "rect": [0, 0, 10, 10],
                        "is_discard": False,
                        "lines": [
                            {
                                "text": "This is a long text that needs to be split",
                                "rect": [0, 0, 10, 10],
                                "type": "text",
                                "is_discard": False
                            }
                        ]
                    }
                ]
            }
        ]
        result = self.splitter.split_text(pages_info)
        self.assertTrue(len(result) > 1)
        self.assertTrue(all(len(chunk["text"]) > 0 for chunk in result))

    def test_complex_page_with_multiple_zone_types(self):
        """Test handling of a complex page with multiple zone types including images, text, titles, and equations."""
        pages_info = [
            {
                "page_info": {
                    "page_no": 1,
                    "page_size": {
                        "width": 612.0,
                        "height": 792.0
                    }
                },
                "zones": [
                    {
                        "rect": [312, 53, 558, 264],
                        "type": "image",
                        "is_discard": False,
                        "lines": []
                    },
                    {
                        "rect": [47, 475, 301, 666],
                        "type": "text",
                        "is_discard": False,
                        "lines": [
                            {
                                "text": "3) Q-A3: Seach performance comparison to distance-based",
                                "rect": [57, 476, 301, 487],
                                "type": "text",
                                "is_discard": False
                            },
                            {
                                "text": "optimization: The recall that a graph can potentially achieve",
                                "rect": [48, 488, 300, 500],
                                "type": "text",
                                "is_discard": False
                            },
                            {
                                "text": "and the number of iterations to obtain a specific recall will",
                                "rect": [48, 500, 301, 511],
                                "type": "text",
                                "is_discard": False
                            },
                            {
                                "text": "vary by the graph construction methods, including the reorder-",
                                "rect": [48, 512, 300, 523],
                                "type": "text",
                                "is_discard": False
                            },
                            {
                                "text": "ing distance criteria in the CAGRA graph optimization. In",
                                "rect": [48, 524, 301, 535],
                                "type": "text",
                                "is_discard": False
                            },
                            {
                                "text": "CAGRA, we reduce the graph optimization time, avoiding",
                                "rect": [47, 536, 301, 547],
                                "type": "text",
                                "is_discard": False
                            },
                            {
                                "text": "distance computation and instead using the initial rank as",
                                "rect": [48, 548, 301, 558],
                                "type": "text",
                                "is_discard": False
                            },
                            {
                                "text": "the distance criteria. So then, does the CAGRA graph have",
                                "rect": [47, 560, 300, 570],
                                "type": "text",
                                "is_discard": False
                            },
                            {
                                "text": "the compatible search performance compared to distance-",
                                "rect": [47, 571, 301, 583],
                                "type": "text",
                                "is_discard": False
                            },
                            {
                                "text": "based optimization? To answer this question, we have tested",
                                "rect": [47, 583, 301, 595],
                                "type": "text",
                                "is_discard": False
                            },
                            {
                                "text": "both rank-based and distance-based reordering during CAGRA",
                                "rect": [47, 595, 300, 606],
                                "type": "text",
                                "is_discard": False
                            },
                            {
                                "text": "graph optimization and measured the throughput and recall",
                                "rect": [48, 608, 300, 618],
                                "type": "text",
                                "is_discard": False
                            },
                            {
                                "text": "of a query search process using the graph, as shown in Fig.",
                                "rect": [47, 619, 299, 631],
                                "type": "text",
                                "is_discard": False
                            },
                            {
                                "text": "5. This confirms the recall-throughput balance is almost the",
                                "rect": [48, 632, 300, 642],
                                "type": "text",
                                "is_discard": False
                            },
                            {
                                "text": "same while the rank-based graph construction time is shorter,",
                                "rect": [47, 643, 300, 655],
                                "type": "text",
                                "is_discard": False
                            },
                            {
                                "text": "as demonstrated in Q-A2.",
                                "rect": [48, 655, 153, 666],
                                "type": "text",
                                "is_discard": False
                            }
                        ]
                    },
                    {
                        "rect": [311, 496, 366, 507],
                        "type": "title",
                        "is_discard": False,
                        "lines": [
                            {
                                "text": "A. Algorithm",
                                "rect": [310, 495, 366, 507],
                                "type": "text",
                                "is_discard": False
                            }
                        ]
                    },
                    {
                        "rect": [311, 512, 563, 621],
                        "type": "text",
                        "is_discard": False,
                        "lines": [
                            {
                                "text": "The CAGRA search algorithm uses a sequential memory",
                                "rect": [320, 513, 563, 524],
                                "type": "text",
                                "is_discard": False
                            },
                            {
                                "text": "buffer consisting of an internal top-M list (typically known",
                                "rect": [311, 525, 563, 536],
                                "type": "text",
                                "is_discard": False
                            },
                            {
                                "text": "as a priority queue in other algorithms) and its candidate list,",
                                "rect": [311, 537, 563, 548],
                                "type": "text",
                                "is_discard": False
                            },
                            {
                                "text": "as shown at the top of Fig. 6. The length of the internal top-M",
                                "rect": [311, 550, 563, 560],
                                "type": "text",
                                "is_discard": False
                            },
                            {
                                "text": "list is M(≥k), and the candidate list is p×d, where p",
                                "rect": [311, 560, 563, 572],
                                "type": "text",
                                "is_discard": False
                            },
                            {
                                "text": "is the number of source nodes of the graph traversed in each",
                                "rect": [310, 572, 564, 584],
                                "type": "text",
                                "is_discard": False
                            },
                            {
                                "text": "iteration, and d is the degree of the CAGRA graph. Each buffer",
                                "rect": [310, 585, 564, 596],
                                "type": "text",
                                "is_discard": False
                            },
                            {
                                "text": "element is a key/value pair containing a node index and the",
                                "rect": [311, 597, 564, 609],
                                "type": "text",
                                "is_discard": False
                            },
                            {
                                "text": "corresponding distance between the node and the query.",
                                "rect": [311, 609, 542, 620],
                                "type": "text",
                                "is_discard": False
                            }
                        ]
                    }
                ]
            }
        ]

        result = self.splitter.split_text(pages_info)

        # Verify basic structure
        self.assertTrue(len(result) > 0)
        for chunk in result:
            self.assertTrue("text" in chunk)
            self.assertTrue("metadata" in chunk)
            
            # Verify metadata format
            metadata = chunk["metadata"]
            self.assertTrue("page" in metadata)
            self.assertTrue("rect" in metadata)
            
            # Verify page info
            page_info = metadata["page"]
            self.assertEqual(page_info["page_num"], 1)
            self.assertEqual(page_info["width"], 612.0)
            self.assertEqual(page_info["height"], 792.0)

        # Print detailed chunk information
        print("\n\n=== Detailed Chunk Analysis ===")
        for i, chunk in enumerate(result, 1):
            print(f"\n{'-'*80}")
            print(f"CHUNK #{i}")
            print(f"{'-'*80}")
            print("TEXT CONTENT:")
            print(f"{chunk['text']}")
            print("\nMETADATA:")
            metadata = chunk["metadata"]
            print(f"  Page Info:")
            print(f"    - Page Number: {metadata['page']['page_num']}")
            print(f"    - Page Width: {metadata['page']['width']}")
            print(f"    - Page Height: {metadata['page']['height']}")
            
            # Rectangle information
            print(f"  Rectangle Coordinates:")
            print(f"    - x1: {metadata['rect']['x1']}")
            print(f"    - y1: {metadata['rect']['y1']}")
            print(f"    - x2: {metadata['rect']['x2']}")
            print(f"    - y2: {metadata['rect']['y2']}")

        # Verify that text content is present
        text_content = " ".join([chunk["text"] for chunk in result])
        self.assertIn("Q-A3", text_content)
        self.assertIn("CAGRA", text_content)
        self.assertIn("algorithm", text_content)
        self.assertIn("graph optimization", text_content)

if __name__ == '__main__':
    unittest.main()
