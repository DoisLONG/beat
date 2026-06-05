# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import json
import logging
from pathlib import Path

from comps.asr.config import GLOSSARY_FILE


logger = logging.getLogger("asr-glossary")


class GlossaryManager:
    def __init__(self, file_path: Path | None = None):
        self.file_path = file_path or GLOSSARY_FILE
        self._ensure_exists()

    def _ensure_exists(self) -> None:
        if self.file_path.exists():
            return
        self.file_path.parent.mkdir(parents=True, exist_ok=True)
        self.file_path.write_text(
            json.dumps(["思创", "高潜人才"], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def get_glossary_terms(self) -> list[str]:
        try:
            payload = json.loads(self.file_path.read_text(encoding="utf-8"))
            return [item for item in payload if isinstance(item, str)]
        except Exception as exc:  # noqa: BLE001
            logger.error(f"Failed to read glossary: {exc}")
            return ["思创", "高潜人才"]

    def add_new_terms(self, terms: list[str]) -> str:
        current = self.get_glossary_terms()
        added = [term for term in terms if term and term not in current]
        if not added:
            return "没有新词需添加"
        current.extend(added)
        self.file_path.write_text(
            json.dumps(current, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return f"已存入新词: {added}"

    def add_term(self, term: str) -> bool:
        return "已存入新词" in self.add_new_terms([term])

    def delete_term(self, term: str) -> bool:
        current = self.get_glossary_terms()
        if term not in current:
            return False
        current.remove(term)
        self.file_path.write_text(
            json.dumps(current, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return True

    def clear_terms(self) -> bool:
        self.file_path.write_text("[]", encoding="utf-8")
        return True

    def search_terms(self, keyword: str) -> list[str]:
        terms = self.get_glossary_terms()
        if not keyword:
            return terms
        return [term for term in terms if keyword in term]

    def import_terms_from_file(self, import_file: Path) -> int:
        if not import_file.exists():
            return 0
        payload = json.loads(import_file.read_text(encoding="utf-8"))
        if not isinstance(payload, list):
            return 0
        current = self.get_glossary_terms()
        added = [term for term in payload if isinstance(term, str) and term not in current]
        if not added:
            return 0
        current.extend(added)
        self.file_path.write_text(
            json.dumps(current, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return len(added)

    def export_terms_to_file(self, export_file: Path) -> bool:
        export_file.parent.mkdir(parents=True, exist_ok=True)
        export_file.write_text(
            json.dumps(self.get_glossary_terms(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return True
