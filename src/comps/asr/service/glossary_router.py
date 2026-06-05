# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import tempfile
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, Query, UploadFile

from comps.asr.config import DATA_DIR
from comps.asr.service.glossary import GlossaryManager


router = APIRouter(prefix="/api/v1/glossary", tags=["glossary"])
_glossary_mgr = GlossaryManager()


@router.get("/terms", response_model=list[str])
def get_all_terms() -> list[str]:
    return _glossary_mgr.get_glossary_terms()


@router.post("/terms")
def add_single_term(term: str = Query(..., description="要添加的专业术语")) -> dict[str, str]:
    if _glossary_mgr.add_term(term):
        return {"message": "添加成功", "term": term}
    raise HTTPException(status_code=409, detail="专业术语已存在")


@router.post("/terms/batch")
def batch_add_terms(terms: list[str] = Query(..., description="要添加的专业术语列表")) -> dict[str, object]:
    result = _glossary_mgr.add_new_terms(terms)
    return {"message": result, "count": len(_glossary_mgr.get_glossary_terms())}


@router.delete("/terms/{term}")
def delete_term(term: str) -> dict[str, str]:
    if _glossary_mgr.delete_term(term):
        return {"message": "删除成功", "term": term}
    raise HTTPException(status_code=404, detail="专业术语不存在")


@router.delete("/terms")
def clear_all_terms() -> dict[str, str]:
    _glossary_mgr.clear_terms()
    return {"message": "清空成功"}


@router.get("/search", response_model=list[str])
def search_terms(keyword: str = Query(..., description="搜索关键词")) -> list[str]:
    return _glossary_mgr.search_terms(keyword)


@router.post("/import")
async def import_terms(file: UploadFile = File(..., description="包含专业术语的JSON文件")) -> dict[str, object]:
    if not (file.filename or "").lower().endswith(".json"):
        raise HTTPException(status_code=400, detail="仅支持JSON文件")
    with tempfile.NamedTemporaryFile(delete=False, suffix=".json") as temp_file:
        temp_file.write(await file.read())
        temp_path = Path(temp_file.name)
    try:
        imported_count = _glossary_mgr.import_terms_from_file(temp_path)
        return {"message": "导入成功", "imported_count": imported_count, "filename": file.filename}
    finally:
        temp_path.unlink(missing_ok=True)


@router.get("/export")
def export_terms(file_path: str | None = Query(None, description="导出文件路径")) -> dict[str, object]:
    export_path = Path(file_path) if file_path else DATA_DIR / "exported_glossary.json"
    _glossary_mgr.export_terms_to_file(export_path)
    return {
        "message": "导出成功",
        "file_path": str(export_path),
        "exported_count": len(_glossary_mgr.get_glossary_terms()),
    }
