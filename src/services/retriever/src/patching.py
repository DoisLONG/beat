# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

from typing import Callable

from .config import logger

from langchain_milvus.vectorstores import Milvus

class MyMilvus(Milvus):
    # the code is just copied from langchain_milvus(0.1.8)
    # and patched the lines between EKBA marks
    def _select_relevance_score_fn(self) -> Callable[[float], float]:
        """
        The 'correct' relevance function
        may differ depending on a few things, including:
        - the distance / similarity metric used by the VectorStore
        - the scale of your embeddings (OpenAI's are unit normed. Many others are not!)
        - embedding dimensionality
        - etc.

        """
        if not self.col or not self.col.indexes:
            raise ValueError(
                "No index params provided. Could not determine relevance function."
            )
        if self._is_multi_embedding or self._is_multi_function:
            raise ValueError(
                "No supported normalization function for multi vectors. "
                "Could not determine relevance function."
            )
        if self._is_sparse:
            raise ValueError(
                "No supported normalization function for sparse indexes. "
                "Could not determine relevance function."
            )

        def _map_l2_to_similarity(l2_distance: float) -> float:
            """Return a similarity score on a scale [0, 1].
            It is recommended that the original vector is normalized,
            Milvus only calculates the value before applying square root.
            l2_distance range: (0 is most similar, 4 most dissimilar)
            See
            https://milvus.io/docs/metric.md?tab=floating#Euclidean-distance-L2
            """
            return 1 - l2_distance / 4.0

        def _map_ip_to_similarity(ip_score: float) -> float:
            """Return a similarity score on a scale [0, 1].
            It is recommended that the original vector is normalized,
            ip_score range: (1 is most similar, -1 most dissimilar)
            See
            https://milvus.io/docs/metric.md?tab=floating#Inner-product-IP
            https://milvus.io/docs/metric.md?tab=floating#Cosine-Similarity
            """
            # --- EKBA ---
            # below is the original line
            #return (ip_score + 1) / 2.0

            # For unnormalized vectors, return raw IP score
            # This preserves the original similarity relationship
            return ip_score
            # --- EKBA ---

        if not self.index_params:
            logger.warning(
                "No index params provided. Could not determine relevance function. "
                "Use L2 distance as default."
            )
            return _map_l2_to_similarity
        indexes_params = self._as_list(self.index_params)
        if len(indexes_params) > 1:
            raise ValueError(
                "No supported normalization function for multi vectors. "
                "Could not determine relevance function."
            )
        # In the left case, the len of indexes_params is 1.
        metric_type = indexes_params[0]["metric_type"]
        if metric_type == "L2":
            return _map_l2_to_similarity
        elif metric_type in ["IP", "COSINE"]:
            return _map_ip_to_similarity
        else:
            raise ValueError(
                "No supported normalization function"
                f" for metric type: {metric_type}."
            )
