# Copyright (C) 2024 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
from typing import List, Dict
from urllib.parse import unquote

from fastapi import Body, Query, File, Form, UploadFile, HTTPException, Request
from fastapi.responses import StreamingResponse
from comps import opea_microservices, register_microservice
from comps.oss_manager.config import FILES_STORED_TYPE
from comps.oss_manager.minio_utils import (
    get_object_metadata_by_uri,
    iter_object_by_uri,
    save_upload_file_minio,
)
from course_routes import add_course_with_videos, update_course_with_videos, delete_course, get_course_list, \
    get_course_info, upload_oss_response, sign_oss_response, add_timestamp_to_file
from material_routes import upload_material_file, update_material_info, delete_material, get_materials_list
from learning_statistics_routes import get_video_learning_statistics, get_user_learning_summary, get_tenant_learning_summary
from comps.oss_manager import oss_manager
from learning_progress_routes import start_learning_video, heartbeat_learning_video, end_learning_video, get_user_course_progress, get_user_learning_progress_list, get_tenant_learning_progress_list
from comps.account.auth import require_auth_dict
from comps.learn.file_access import build_content_disposition, guess_content_type, guess_filename
from mysql_client import MySQLClient
from config import MYSQL_CONFIG


def _parse_range_header(range_header: str, file_size: int) -> tuple[int, int]:
    """解析单个 HTTP Range 请求，供视频拖动播放使用。"""
    if not range_header.startswith("bytes="):
        raise ValueError("仅支持 bytes Range")

    range_value = range_header[6:].strip()
    if "," in range_value:
        raise ValueError("暂不支持多段 Range")

    start_text, sep, end_text = range_value.partition("-")
    if not sep:
        raise ValueError("非法 Range 格式")

    if start_text == "" and end_text == "":
        raise ValueError("非法 Range 格式")

    if start_text == "":
        suffix_length = int(end_text)
        if suffix_length <= 0:
            raise ValueError("非法 Range 长度")
        if suffix_length >= file_size:
            return 0, file_size - 1
        return file_size - suffix_length, file_size - 1

    start = int(start_text)
    if start < 0 or start >= file_size:
        raise ValueError("Range 起始位置越界")

    if end_text == "":
        return start, file_size - 1

    end = int(end_text)
    if end < start:
        raise ValueError("Range 结束位置非法")
    return start, min(end, file_size - 1)


def _build_streaming_response(
    decoded_uri: str,
    content_type: str,
    headers: dict[str, str],
    size: int | None,
    range_header: str | None,
):
    response_headers = {**headers, "Accept-Ranges": "bytes"}

    if size is None or range_header is None:
        if size is not None:
            response_headers["Content-Length"] = str(size)
        if decoded_uri.startswith("minio://"):
            return StreamingResponse(
                iter_object_by_uri(decoded_uri),
                media_type=content_type,
                headers=response_headers,
            )
        return StreamingResponse(
            oss_manager.iter_object(decoded_uri),
            media_type=content_type,
            headers=response_headers,
        )

    try:
        start, end = _parse_range_header(range_header, size)
    except ValueError as exc:
        raise HTTPException(
            status_code=416,
            detail=str(exc),
            headers={"Content-Range": f"bytes */{size}"},
        ) from exc

    content_length = end - start + 1
    response_headers["Content-Length"] = str(content_length)
    response_headers["Content-Range"] = f"bytes {start}-{end}/{size}"

    if decoded_uri.startswith("minio://"):
        iterator = iter_object_by_uri(decoded_uri, offset=start, length=content_length)
    else:
        iterator = oss_manager.iter_object(decoded_uri, offset=start, length=content_length)

    return StreamingResponse(
        iterator,
        media_type=content_type,
        headers=response_headers,
        status_code=206,
    )

@register_microservice(
    name="opea_service@prepare_company_mysql",
    endpoint="/api/v1/course/add",
    host="0.0.0.0",
    port=7010,
)
@require_auth_dict()
async def add_course_route(
    request: Request,
    title: str = Body(..., embed=True, description="课程标题（必填）"),
    code: str = Body(None, embed=True, description="课程编码（可选）"),
    category: str = Body(None, embed=True, description="课程分类（可选）"),
    cover_url: str = Body(None, embed=True, description="封面图URL（可选）"),
    description: str = Body(None, embed=True, description="课程描述（可选）"),
    tags: List[str] = Body(None, embed=True, description="课程标签（可选）"),
    status: str = Body("draft", embed=True, description="课程状态（默认draft）"),
    videos: List[Dict] = Body(..., embed=True, description="视频信息列表（必填）"),
    keywordslist: List[Dict] = Body(None, embed=True, description="关键词列表（可选）"),
    position_id: int = Body(None, embed=True, description="关联岗位ID（可选）"),
    user: Dict = None  # 从装饰器注入的用户信息（包含tenant_id）
):
    return await add_course_with_videos(
        title=title,
        code=code,
        category=category,
        cover_url=cover_url,
        description=description,
        tags=tags,
        status=status,
        videos=videos,
        keywordslist=keywordslist,
        position_id=position_id,
        current_user=user
    )

@register_microservice(
    name="opea_service@prepare_company_mysql",
    endpoint="/api/v1/course/update",
    host="0.0.0.0",
    port=7010,
)
@require_auth_dict()
async def update_course_route(
    request: Request,
    course_id: str = Body(..., embed=True, description="课程ID（必填）"),
    title: str = Body(None, embed=True, description="新课程标题（可选）"),
    category: str = Body(None, embed=True, description="新课程分类（可选）"),
    description: str = Body(None, embed=True, description="新课程描述（可选）"),
    status: str = Body(None, embed=True, description="新课程状态（可选）"),
    videos: List[Dict] = Body(None, embed=True, description="新视频信息列表（可选）"),
    keywordslist: List[Dict] = Body(None, embed=True, description="新关键词列表（可选）"),
    position_id: int = Body(None, embed=True, description="新关联岗位ID（可选）"),
    user: Dict = None  # 从装饰器注入的用户信息（包含tenant_id）
):
    """更新课程（自动更新版本号）"""
    return await update_course_with_videos(
        course_id=course_id,
        title=title,
        category=category,
        description=description,
        status=status,
        videos=videos,
        keywordslist=keywordslist,
        position_id=position_id,
        current_user=user
    )


@register_microservice(
    name="opea_service@prepare_company_mysql",
    endpoint="/api/v1/course/delete/{course_id}",
    host="0.0.0.0",
    port=7010,
    methods=["DELETE"],
)
@require_auth_dict()
async def delete_course_route(request: Request,course_id: str,user: Dict = None):
    """删除课程（逻辑删除）"""
    return await delete_course(course_id=course_id,
        current_user=user)


@register_microservice(
    name="opea_service@prepare_company_mysql",
    endpoint="/api/v1/learn/categories",
    host="0.0.0.0",
    port=7010,
    methods=["GET"],
)
@require_auth_dict()
async def get_learn_categories_route(
    request: Request,
    user: Dict = None,
):
    """获取课程/素材分类列表（按 JWT.lang 返回对应语种）"""
    lang = (user or {}).get("lang") or "zh"
    if lang not in ("zh", "en", "th"):
        lang = "zh"
    db_client = MySQLClient(MYSQL_CONFIG)
    return {
        "code": 0,
        "message": "success",
        "data": db_client.get_category_options(lang)
    }


@register_microservice(
    name="opea_service@prepare_company_mysql",
    endpoint="/api/v1/course/list",
    host="0.0.0.0",
    port=7010,
    methods=["GET"],
)
@require_auth_dict()
async def get_course_list_route(
    request: Request,
    keyword: str = Query(None, description="模糊搜索（标题/编码）"),
    category: str = Query(None, description="分类"),
    status: str = Query(None, description="课程状态（draft/published/archived）"),
    position_id: int = Query(None, description="岗位ID（选填）"),
    department_id: int = Query(None, description="部门ID（选填）"),
    company_id: int = Query(None, description="公司ID（选填）"),
    position_name: str = Query(None, description="岗位名称（模糊匹配，选填）"),
    department_name: str = Query(None, description="部门名称（模糊匹配，选填）"),
    company_name: str = Query(None, description="公司名称（模糊匹配，选填）"),
    page: int = Query(1, description="当前页，默认1"),
    page_size: int = Query(20, description="每页数量，默认20"),
    user: Dict = None
):
    """课程列表查询（关联岗位+部门+公司表）"""
    return await get_course_list(
        keyword=keyword,
        category=category,
        status=status,
        position_id=position_id if position_id is not None else (user.get('position_id') if user else None),
        department_id=department_id,
        company_id=company_id,
        position_name=position_name,
        department_name=department_name,
        company_name=company_name,
        page=page,
        page_size=page_size,
        current_user=user
    )


@register_microservice(
    name="opea_service@prepare_company_mysql",
    endpoint="/api/v1/course/info/{course_id}",
    host="0.0.0.0",
    port=7010,
    methods=["GET"],
)
@require_auth_dict()
async def get_course_info_route(request: Request,course_id: str,
    user: Dict = None):
    """课程详情"""
    return await get_course_info(course_id,
        current_user=user)


@register_microservice(
    name="opea_service@prepare_company_mysql",
    endpoint="/api/v1/materials/upload",
    host="0.0.0.0",
    port=7010,
)
@require_auth_dict()  # 添加认证装饰器
async def upload_material_route(
        request: Request,
        file: UploadFile = File(..., description="文件本身（必填）"),
        title: str = Form(..., description="资料名称（必填）"),
        description: str = Form(None, description="说明（选填）"),
        category: str = Form(None, description="分类（选填）"),
        course_id: str = Form(None, description="关联课程ID（选填）"),
        position_id: int = Form(None, description="关联岗位ID（选填）"),
        size: int = Form(None, description="文件大小（选填）"),
        user: Dict = None  # 从装饰器注入的用户信息（包含tenant_id）
):
    """上传学习资料文件（包含租户信息）"""
    # 在实际应用中，这里需要处理文件上传到OSS的逻辑
    temp_file_info = await add_timestamp_to_file(file)
    if FILES_STORED_TYPE == "oss":
        _object_key, file_url, _share_url = await oss_manager.oss_upload(temp_file_info, "-1")
    else:
        file_url_infos = await save_upload_file_minio(temp_file_info,"-1")
        file_url = file_url_infos[2]

    file_type = file.filename.split('.')[-1] if '.' in file.filename else None

    return await upload_material_file(
        title=title,
        file_url=file_url,
        description=description,
        category=category,
        course_id=course_id,
        position_id=position_id,
        file_type=file_type,
        size=size,
        current_user=user
    )


@register_microservice(
    name="opea_service@prepare_company_mysql",
    endpoint="/api/v1/materials/update",
    host="0.0.0.0",
    port=7010,
)
@require_auth_dict()  # 添加认证装饰器
async def update_material_info_route(
    request: Request,
    material_id: str = Body(..., embed=True, description="资料ID（必填）"),
    title: str = Body(None, embed=True, description="新资料标题（可选）"),
    description: str = Body(None, embed=True, description="新资料描述（可选）"),
    category: str = Body(None, embed=True, description="新资料分类（可选）"),
    course_id: str = Body(None, embed=True, description="新关联课程ID（可选）"),
    position_id: int = Body(None, embed=True, description="新关联岗位ID（可选，0表示清除关联）"),
    user: Dict = None  # 从装饰器注入的用户信息（包含tenant_id）
):
    """更新学习资料信息（包含租户验证）"""
    return await update_material_info(
        material_id=material_id,
        title=title,
        description=description,
        category=category,
        course_id=course_id,
        position_id=position_id,
        current_user=user
    )


@register_microservice(
    name="opea_service@prepare_company_mysql",
    endpoint="/api/v1/materials/delete/{material_id}",
    host="0.0.0.0",
    port=7010,
    methods=["DELETE"],
)
@require_auth_dict()  # 添加认证装饰器
async def delete_material_route(
    request: Request,
    material_id: str,
    user: Dict = None  # 从装饰器注入的用户信息（包含tenant_id）
):
    """删除学习资料（包含租户验证）"""
    return await delete_material(
        material_id=material_id,
        current_user=user
    )


@register_microservice(
    name="opea_service@prepare_company_mysql",
    endpoint="/api/v1/materials/list",
    host="0.0.0.0",
    port=7010,
    methods=["GET"],
)
@require_auth_dict()  # 添加认证装饰器
async def get_materials_list_route(
    request: Request,
    category: str = Query(None, description="分类（选填）"),
    keyword: str = Query(None, description="关键词（选填）"),
    course_id: str = Query(None, description="课程ID（选填）"),
    position_id: int = Query(None, description="岗位ID（选填）"),
    department_id: int = Query(None, description="部门ID（选填）"),
    company_id: int = Query(None, description="公司ID（选填）"),
    position_name: str = Query(None, description="岗位名称（模糊匹配，选填）"),
    department_name: str = Query(None, description="部门名称（模糊匹配，选填）"),
    company_name: str = Query(None, description="公司名称（模糊匹配，选填）"),
    page: int = Query(1, description="当前页，默认1"),
    page_size: int = Query(20, description="每页数量，默认20"),
    user: Dict = None  # 从装饰器注入的用户信息（包含tenant_id）
):
    """学习资料列表查询（关联岗位+部门+公司表，包含租户筛选）"""
    return await get_materials_list(
        category=category,
        keyword=keyword,
        course_id=course_id,
        position_id=user.get('position_id') if user else None,
        department_id=department_id,
        company_id=company_id,
        position_name=position_name,
        department_name=department_name,
        company_name=company_name,
        page=page,
        page_size=page_size,
        current_user=user
    )

@register_microservice(
    name="opea_service@prepare_company_mysql",
    endpoint="/api/v1/statistics/video-time",
    host="0.0.0.0",
    port=7010,
    methods=["GET"],
)
@require_auth_dict()  # 添加认证装饰器
async def get_video_learning_statistics_route(
        request: Request,
        start_date: str = Query(None, description="开始日期（yyyy-MM-dd，可选）"),
        end_date: str = Query(None, description="结束日期（yyyy-MM-dd，可选）"),
        course_id: str = Query(None, description="课程ID（可选）"),
        page: int = Query(1, description="当前页，默认1"),
        page_size: int = Query(20, description="每页数量，默认20"),
        user: Dict = None  # 从装饰器注入的用户信息
):
    """6.1 视频学习统计分页查询（管理端）"""
    return await get_video_learning_statistics(
        start_date=start_date,
        end_date=end_date,
        course_id=course_id,
        current_user=user,  # 传递用户信息
        page=page,
        page_size=page_size
    )


@register_microservice(
    name="opea_service@prepare_company_mysql",
    endpoint="/api/v1/user/learning/summary",
    host="0.0.0.0",
    port=7010,
    methods=["GET"],
)
@require_auth_dict()  # 添加认证装饰器
async def get_user_learning_summary_route(
        request: Request,
        user_id: int = Query(None, description="用户ID（选填，不传默认当前登录用户）"),
        user: Dict = None  # 从装饰器注入的用户信息
):
    """6.2 用户学习统计概览（个人仪表盘）"""
    return await get_user_learning_summary(user_id, user)  # 传递用户信息


@register_microservice(
    name="opea_service@prepare_company_mysql",
    endpoint="/api/v1/learning/progress/all",
    host="0.0.0.0",
    port=7010,
    methods=["GET"],
)
@require_auth_dict()
async def get_admin_learning_progress_route(
        request: Request,
        page: int = Query(1, description="当前页，默认1"),
        page_size: int = Query(20, description="每页数量，默认20"),
        user: Dict = None,
):
    """管理端：查询租户范围内所有用户课程学习进度（租户1查全量）。"""
    return await get_tenant_learning_progress_list(
        current_user=user,
        page=page,
        page_size=page_size,
    )


@register_microservice(
    name="opea_service@prepare_company_mysql",
    endpoint="/api/v1/user/learning/summary/all",
    host="0.0.0.0",
    port=7010,
    methods=["GET"],
)
@require_auth_dict()
async def get_admin_user_learning_summary_route(
        request: Request,
        page: int = Query(1, description="当前页，默认1"),
        page_size: int = Query(20, description="每页数量，默认20"),
        user: Dict = None,
):
    """管理端：查询租户范围内所有用户学习汇总（租户1查全量）。"""
    return await get_tenant_learning_summary(
        current_user=user,
        page=page,
        page_size=page_size,
    )

@register_microservice(
    name="opea_service@prepare_company_mysql",
    endpoint="/api/v1/oss/upload",
    host="0.0.0.0",
    port=7010,
)
async def upload_oss(
        file: UploadFile = File(..., description="文件本身（必填）"),
):
    return await upload_oss_response(file)

@register_microservice(
    name="opea_service@prepare_company_mysql",
    endpoint="/api/v1/oss/sign",
    host="0.0.0.0",
    port=7010,
)
async def sign_oss(
        oss_uri: str = Body(..., embed=True, description="oss uri（必填）"),
):
    return await sign_oss_response(oss_uri)


@register_microservice(
    name="opea_service@prepare_company_mysql",
    endpoint="/api/v1/files/access",
    host="0.0.0.0",
    port=7010,
    methods=["GET"],
)
async def access_file_route(
    request: Request,
    uri: str = Query(..., description="内部文件 URI，仅支持 minio:// 或 oss://，uri 应该做 encodeURIComponent"),
    download: bool = Query(False, description="是否按附件下载"),
    filename: str | None = Query(None, description="覆盖下载文件名"),
):

    decoded_uri = unquote(uri).strip()
    if not decoded_uri.startswith(("minio://", "oss://")):
        raise HTTPException(status_code=400, detail="仅支持内部存储 URI")

    # db_client = MySQLClient(MYSQL_CONFIG)
    # access_record = db_client.query_accessible_file_reference(
    #     file_uri=decoded_uri,
    #     tenant_id=tenant_id,
    #     position_id=user.get("position_id"),
    # )
    # if not access_record:
    #     raise HTTPException(status_code=403, detail="无权访问该文件")

    resolved_filename = filename or guess_filename(decoded_uri)
    content_type = guess_content_type(resolved_filename)
    headers = {
        "Content-Disposition": build_content_disposition(resolved_filename, download),
        "Cache-Control": "private, max-age=300",
    }
    range_header = request.headers.get("range") if request else None

    if decoded_uri.startswith("minio://"):
        metadata = get_object_metadata_by_uri(decoded_uri)
        content_type = str(metadata.get("content_type") or content_type)
        size = metadata.get("size")
        return _build_streaming_response(
            decoded_uri=decoded_uri,
            content_type=content_type,
            headers=headers,
            size=size,
            range_header=range_header,
        )

    metadata = oss_manager.get_object_metadata(decoded_uri)
    content_type = str(metadata.get("content_type") or content_type)
    size = metadata.get("size")
    return _build_streaming_response(
        decoded_uri=decoded_uri,
        content_type=content_type,
        headers=headers,
        size=size,
        range_header=range_header,
    )

@register_microservice(
    name="opea_service@prepare_company_mysql",
    endpoint="/api/v1/learn/video/start",
    host="0.0.0.0",
    port=7010,
)
@require_auth_dict()  # 添加认证装饰器
async def start_learning_video_route(
    request: Request,
    course_id: str = Body(..., embed=True, description="课程ID（必填）"),
    video_id: str = Body(..., embed=True, description="视频ID（必填）"),
    from_position: int = Body(0, embed=True, description="起始播放位置（秒，可选）"),
    user: Dict = None  # 从装饰器注入的用户信息
):
    """5.1 开始学习（视频）。用户与租户从 JWT 取"""
    return await start_learning_video(
        course_id=course_id,
        video_id=video_id,
        from_position=from_position,
        current_user=user
    )


@register_microservice(
    name="opea_service@prepare_company_mysql",
    endpoint="/api/v1/learning/video/heartbeat",
    host="0.0.0.0",
    port=7010,
)
@require_auth_dict()
async def heartbeat_learning_video_route(
    request: Request,
    session_id: str = Body(..., embed=True, description="会话ID（必填）"),
    session_watch_seconds: int = Body(..., embed=True, description="本次会话累计观看时长（秒，必填）"),
    position: int = Body(0, embed=True, description="当前播放器位置（秒，可选）"),
    is_completed: bool = Body(False, embed=True, description="是否已完整看完（可选）"),
    user: Dict = None
):
    """5.2 视频学习心跳。按累计值上报，服务端按差值累计"""
    return await heartbeat_learning_video(
        session_id=session_id,
        session_watch_seconds=session_watch_seconds,
        position=position,
        is_completed=is_completed,
        current_user=user
    )


@register_microservice(
    name="opea_service@prepare_company_mysql",
    endpoint="/api/v1/learning/video/end",
    host="0.0.0.0",
    port=7010,
)
@require_auth_dict()  # 添加认证装饰器
async def end_learning_video_route(
    request:Request,
    session_id: str = Body(..., embed=True, description="会话ID（必填）"),
    session_watch_seconds: int = Body(..., embed=True, description="本次会话累计观看时长（秒，必填）"),
    position: int = Body(0, embed=True, description="当前播放器位置（秒，可选）"),
    is_completed: bool = Body(False, embed=True, description="是否完整看完（可选）"),
    user: Dict = None  # 从装饰器注入的用户信息
):
    """5.3 结束学习（视频）。按累计值收尾，避免与心跳重复累计"""
    return await end_learning_video(
        session_id=session_id,
        session_watch_seconds=session_watch_seconds,
        position=position,
        is_completed=is_completed,
        current_user=user
    )

@register_microservice(
    name="opea_service@prepare_company_mysql",
    endpoint="/api/v1/user/learning/progress",
    host="0.0.0.0",
    port=7010,
    methods=["GET"]
)
@require_auth_dict()  # 添加认证装饰器
async def get_user_course_progress_route(
    request: Request,
    course_id: str = Query(..., description="课程ID（必填）"),
    user: Dict = None  # 从装饰器注入的用户信息
):
    """5.4 查询课程学习进度（个人）。固定查询当前登录用户"""
    return await get_user_course_progress(
        course_id=course_id,
        current_user=user
    )

@register_microservice(
    name="opea_service@prepare_company_mysql",
    endpoint="/api/v1/learning/progress",
    host="0.0.0.0",
    port=7010,
    methods=["GET"],
)
@require_auth_dict()  # 添加认证装饰器
async def get_user_learning_progress_list_route(
    request:Request,
    course_id: str = Query(None, description="课程ID（选填，不传则返回用户所有课程概览）"),
    user_id: int = Query(None, description="用户ID（选填，不传默认当前登录用户）"),
    page: int = Query(1, description="当前页，默认1"),
    page_size: int = Query(20, description="每页数量，默认20"),
    user: Dict = None  # 从装饰器注入的用户信息
):
    """5.5 查询用户课程学习进度列表。默认查自己，可选按 user_id 查指定用户"""
    return await get_user_learning_progress_list(
        course_id=course_id,
        user_id=user_id,
        current_user=user,
        page=page,
        page_size=page_size
    )

if __name__ == "__main__":
    opea_microservices["opea_service@prepare_company_mysql"].start()
