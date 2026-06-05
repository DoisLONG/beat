# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

import os
import time
import traceback
from typing import Dict, Any

from openai import OpenAI

from comps import CustomLogger
from comps.dataprep.config import ACCESS_KEY_ID, ACCESS_KEY_SECRET, LLM_EXTRA_BODY
from comps.dataprep.loaders.loader import OpGuidePdfDataLoader, ERDPdfDataLoader, download_oss_to_temp, cleanup_tmp_dir
from alibabacloud_docmind_api20220711.client import Client as DocmindClient
from alibabacloud_docmind_api20220711 import models as docmind_models
from alibabacloud_tea_openapi import models as open_api_models
from alibabacloud_tea_util import models as util_models
from alibabacloud_credentials.client import Client as CredClient
from alibabacloud_tea_util.client import Client as UtilClient

logger = CustomLogger("dataprep-aliyun-loader", os.getenv("LOG_LEVEL", "INFO"))

class OpGuidePdfDataAliyunLoader(OpGuidePdfDataLoader):
    """
    阿里云版操作规程PDF加载器
    """
    def preprocess_data(self,file_path:str,**kwargs):
        """
        Preprocess the loaded Operation Guide data.
        """
        parser = DocmindParser(
            # 通过credentials获取配置中的AccessKey ID
            access_key_id=ACCESS_KEY_ID,
            # 通过credentials获取配置中的AccessKey Secret
            access_key_secret=ACCESS_KEY_SECRET
        )
        content = parser.parse_layouts(parser.run_and_wait(file_path))
        return content


class ERDPdfDataAliyunLoader(ERDPdfDataLoader):
    """
    阿里云版应急预案PDF加载器
    """
    async def load_data(self, file_path: str,**kwargs):
        """从 OSS 获取 PDF，判断内容结构后解析返回结果"""
        db_client = kwargs.get("db_client")
        sop_id = kwargs.get("sop_id")
        tmp_dir = None
        temp_pdf_path = None
        try:
            tmp_dir, temp_pdf_path = await download_oss_to_temp(file_path, os.path.basename(file_path) or "input.pdf")
            parser = DocmindParser(
                # 通过credentials获取配置中的AccessKey ID
                access_key_id=ACCESS_KEY_ID,
                # 通过credentials获取配置中的AccessKey Secret
                access_key_secret=ACCESS_KEY_SECRET
            )
            md_content = parser.parse_layouts(parser.run_and_wait(temp_pdf_path))
            flag, tables = self.validate_headers(md_content)
            if db_client and sop_id:
                db_client.update_percent_by_id(sop_id, "30%", lang=kwargs.get("lang", "zh"))
            result = self.preprocess_data(file_path=temp_pdf_path, flag=flag, tables=tables, text=md_content)
            return result
        except Exception as e:
            logger.error(f"ERD PDF 数据加载失败: {file_path}, 错误: {e}")
            raise
        finally:
            cleanup_tmp_dir(tmp_dir)

class DocmindParser:
    def __init__(self, access_key_id: str, access_key_secret: str):
        cred = CredClient()
        config = open_api_models.Config(
            access_key_id=access_key_id,
            access_key_secret=access_key_secret
        )
        config.endpoint = "docmind-api.cn-hangzhou.aliyuncs.com"
        self.client = DocmindClient(config)

    def submit_job(self, filepath: str) -> str:
        """提交解析任务并返回 job_id"""
        request = docmind_models.SubmitDocParserJobAdvanceRequest(
            file_url_object=open(filepath, "rb"),
            file_name_extension=filepath.split(".")[-1],
            llm_enhancement=True,
            output_html_table=True
        )
        runtime = util_models.RuntimeOptions()

        try:
            response = self.client.submit_doc_parser_job_advance(request, runtime)
            job_id = response.body.data.id
            logger.info(f"提交成功，job id = {job_id}")
            return job_id
        except Exception as e:
            UtilClient.assert_as_string(e)

    def get_result(self, job_id: str,layout_step_size:int,layout_num:int):
        """查询解析结果"""
        request = docmind_models.GetDocParserResultRequest(
            id=job_id,
            layout_step_size=layout_step_size,
            layout_num=layout_num
        )
        try:
            response = self.client.get_doc_parser_result(request)
            return response
        except Exception as e:
            UtilClient.assert_as_string(e)

    def run_and_wait(self, filepath: str, interval: int = 3, timeout: int = 300):
        """
        提交任务并轮询结果，直到完成或超时。
        interval: 每次轮询间隔秒数
        timeout: 超时时间，默认 5 分钟
        """
        job_id = self.submit_job(filepath)

        logger.info("开始轮询任务状态...")

        while True:
            query_result = self.query_status(job_id)
            status = query_result.get("Status")
            processing = query_result.get("Processing")
            logger.info(f"当前状态: {status},进度：{processing}")
            if status == "success":
                resp = self.get_result(job_id,3000,0)
                status = resp.status_code   # 0 运行中, 1成功, 2失败
                # 成功
                if status == 200 and len(resp.body.data.get("layouts")) != 0 :
                    logger.info("正常返回，解析完成")
                    return resp.body.data
                else:
                    raise RuntimeError(f"Docmind 解析失败: {resp}")
            else:
                logger.info(f"等待中........{job_id}")
                time.sleep(interval)

    def parse_layouts(self, data: dict) -> str:
        """
        解析返回的 data，抽取:
        - 所有 type == 'text' 的 markdownContent
        - 所有 type == 'table' 的 llmResult（若缺失则拼接单元格文字）
        最终按行组合为超长文本。
        """
        result_lines = []
        for layout in data.get("layouts", []):
            layout_type = layout.get("type")
            sub_type = layout.get("subType")
            if layout_type == "title":
            #     content = (layout.get("markdownContent")
            #                or layout.get("text")
            #                or "").strip()
            #     if content:
            #         result_lines.append(content)
                result_lines.append("")
                content = layout.get("text").strip()
            elif layout_type == "table":
                content = (layout.get("markdownContent")
                           or layout.get("text")
                           or "").strip()
            elif sub_type == "picture":
                continue
            else:
                content = layout.get("text").strip()

            if content:
                result_lines.append(content)
            # elif layout_type == "table":
            #     llm_result = layout.get("markdownContent")
            #     if not llm_result:
            #         # 回退：拼接每个单元格的文本/markdownContent
            #         cell_texts = []
            #         for cell in layout.get("cells", []):
            #             for inner in cell.get("layouts", []):
            #                 cell_content = (inner.get("markdownContent")
            #                                 or inner.get("text")
            #                                 or "").strip()
            #                 if cell_content:
            #                     cell_texts.append(cell_content)
            #         if cell_texts:
            #             llm_result = "\t".join(cell_texts)
            #     if llm_result:
            #         result_lines.append(str(llm_result).strip())
        return "\n".join(result_lines)

    def query_status(self, job_id: str) -> Dict[str, Any]:
        """查询任务处理进度/状态"""
        req = docmind_models.QueryDocParserStatusRequest(id=job_id)
        try:
            resp = self.client.query_doc_parser_status(req)
            data = resp.body.data or {}
            return {
                "Status": data.status,
                "NumberOfSuccessfulParsing": data.number_of_successful_parsing,
                "Processing": data.processing,
                "PageCountEstimate": data.page_count_estimate
            }
        except Exception as e:
            UtilClient.assert_as_string(traceback.format_stack())
