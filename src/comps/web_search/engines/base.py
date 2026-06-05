# Copyright (C) 2024 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
from abc import ABC, abstractmethod
from typing import List, Dict

class BaseSearch(ABC):
    name: str

    @abstractmethod
    async def search(self, query: str, count: int = 5) -> List[Dict]:
        pass
