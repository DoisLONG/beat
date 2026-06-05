# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass

from comps.asr.config import ASR_REFINE_BATCH_SIZE, REFINE_BATCH_WORKERS
from comps.asr.models import ASRCorrectionResult, ASRSegment, RefinedSegment, TextRefineResponse
from comps.asr.service.glossary import GlossaryManager
from comps.asr.service.llm_factory import LLMFactory


@dataclass(frozen=True)
class RefineWindow:
    segments: list[ASRSegment]
    owned_ids: set[str]


class RefineAgentService:
    def __init__(self, glossary_mgr: GlossaryManager):
        self.glossary_mgr = glossary_mgr
        self.agent = None
        self._initialize_agent()

    def _initialize_agent(self) -> None:
        from agno.agent import Agent

        glossary_terms = self.glossary_mgr.get_glossary_terms()
        self.agent = Agent(
            model=LLMFactory.create_model(),
            tool_choice=None,
            description="ASR文本矫正专家",
            output_schema=ASRCorrectionResult,
            use_json_mode=True,
            instructions=[
                f"""
                你是技术领域 ASR 文本纠错器，只能输出 JSON。

                【已知专业词库】：
                {",".join(glossary_terms)}

                【硬约束（必须全部满足）】：
                1. 返回 refined_segments 的数量、顺序必须与输入 segments 完全一致。
                2. 每条的 id/start/end 必须与输入一致，不可修改。
                3. 只允许修改 refined_text，不允许合并、拆分、删除、增补片段。
                4. 不确定时保持原文，不要猜测术语。
                5. 仅当高置信且属于领域词时，才写入 new_terms_added。

                【纠错优先级】：
                A. 术语纠错（结合词库与上下文）
                B. 同音错字与明显病句
                C. 标点、单位与数字规范
                """
            ],
        )

    @staticmethod
    def _estimate_total_duration(asr_segments: list[ASRSegment]) -> float:
        if not asr_segments:
            return 0.0
        return max(0.0, asr_segments[-1].end - asr_segments[0].start)

    def _build_windows(self, asr_segments: list[ASRSegment]) -> list[RefineWindow]:
        if not asr_segments:
            return []

        batch_size = max(1, ASR_REFINE_BATCH_SIZE)
        total_duration = self._estimate_total_duration(asr_segments)
        if len(asr_segments) <= batch_size or total_duration <= 90.0:
            return [RefineWindow(segments=asr_segments, owned_ids={segment.id for segment in asr_segments})]

        overlap = min(2, max(1, batch_size // 4))
        step = max(1, batch_size - overlap)
        windows: list[RefineWindow] = []
        total_segments = len(asr_segments)

        for start in range(0, total_segments, step):
            end = min(total_segments, start + batch_size)
            batch = asr_segments[start:end]
            if not batch:
                continue

            owned_start = start if start == 0 else start + overlap
            owned_end = end if end == total_segments else end - overlap
            if owned_start >= owned_end:
                owned_start = start
                owned_end = end

            owned_ids = {segment.id for segment in asr_segments[owned_start:owned_end]}
            if not owned_ids:
                owned_ids = {segment.id for segment in batch}

            windows.append(RefineWindow(segments=batch, owned_ids=owned_ids))
            if end == total_segments:
                break

        return windows

    @staticmethod
    def _build_batch_prompt(batch: list[ASRSegment], owned_ids: set[str]) -> str:
        prompt_payload = {
            "segments": [segment.model_dump() for segment in batch],
            "owned_segment_ids": sorted(owned_ids),
            "note": (
                "segments 是带上下文窗口的数据。请返回全部 segments 的修正结果；"
                "每条必须保留 id/start/end，不可缺失。"
            ),
        }
        return "待处理数据 batch:\n" + json.dumps(prompt_payload, ensure_ascii=False, indent=2)

    def _add_fallback_segments(
        self,
        target_list: list[RefinedSegment],
        source_batch: list[ASRSegment],
        ) -> None:
        for segment in source_batch:
            target_list.append(
                RefinedSegment(
                    id=segment.id,
                    start=segment.start,
                    end=segment.end,
                    original_text=segment.text,
                    refined_text=segment.text,
                )
            )

    @staticmethod
    def _select_owned_segments(
        refined_segments: list[RefinedSegment],
        batch: list[ASRSegment],
        owned_ids: set[str],
    ) -> list[RefinedSegment]:
        refined_map = {segment.id: segment for segment in refined_segments}
        selected: list[RefinedSegment] = []
        for source_segment in batch:
            if source_segment.id not in owned_ids:
                continue
            selected_segment = refined_map.get(source_segment.id)
            if selected_segment is None:
                selected_segment = RefinedSegment(
                    id=source_segment.id,
                    start=source_segment.start,
                    end=source_segment.end,
                    original_text=source_segment.text,
                    refined_text=source_segment.text,
                )
            selected.append(selected_segment)
        return selected

    def process(self, asr_segments: list[ASRSegment]) -> TextRefineResponse:
        try:
            if not self.agent:
                self._initialize_agent()

            all_refined_segments: list[RefinedSegment] = []
            all_new_terms: list[str] = []
            windows = self._build_windows(asr_segments)

            def process_batch(window: RefineWindow) -> tuple[list[RefinedSegment], list[str]]:
                batch = window.segments
                try:
                    run_output = self.agent.run(
                        self._build_batch_prompt(batch, window.owned_ids),
                        output_schema=TextRefineResponse,
                    )
                    result: TextRefineResponse = run_output.content
                    if result.status == "success" and len(result.refined_segments) == len(batch):
                        return self._select_owned_segments(result.refined_segments, batch, window.owned_ids), result.new_terms_added or []
                except Exception:  # noqa: BLE001
                    pass
                fallback: list[RefinedSegment] = []
                self._add_fallback_segments(fallback, batch)
                return self._select_owned_segments(fallback, batch, window.owned_ids), []

            with ThreadPoolExecutor(max_workers=REFINE_BATCH_WORKERS) as executor:
                futures = [executor.submit(process_batch, window) for window in windows]
                for future in futures:
                    batch_refined, batch_terms = future.result()
                    all_refined_segments.extend(batch_refined)
                    all_new_terms.extend(batch_terms)

            if all_new_terms:
                self.glossary_mgr.add_new_terms(sorted(set(all_new_terms)))

            return TextRefineResponse(
                original_segments=asr_segments,
                refined_segments=all_refined_segments,
                new_terms_added=sorted(set(all_new_terms)),
                status="success",
                message="全部批次处理完成",
            )
        except Exception as exc:  # noqa: BLE001
            return TextRefineResponse(
                original_segments=asr_segments,
                refined_segments=[],
                new_terms_added=[],
                status="error",
                message=f"分批处理失败: {exc}",
            )
