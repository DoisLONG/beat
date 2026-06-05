# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

# prompts.py
import os
from typing import Dict, Optional

# ==============================
# 泰文提示词 (Thai Prompts)
# ==============================

THAI_PROMPTS = {
    "JUDGE_FILL_IN_BLANK": """
        คุณเป็นผู้ช่วยฝึกซ้อม กรุณาตัดสินว่าคำตอบของผู้ใช้ถูกต้องตามความหมายหรือไม่:
        - หากคำตอบของผู้ใช้แสดงขั้นตอนหรือความหมายเดียวกันกับคำตอบที่ถูกต้อง แม้จะใช้คำต่างกัน ก็ถือว่าถูกต้อง คะแนนเต็ม {question_score}
        - หากความหมายหลักของคำตอบผู้ใช้ไม่ตรงกับคำตอบที่ถูกต้อง ถือว่าผิด คะแนน 0
        - ถ้าถูกต้อง คะแนน {question_score}

        คำถาม: {question_text}
        คำตอบที่ถูกต้อง: {standard_answer}
        คำตอบผู้ใช้: {user_answer}

        กรุณาแสดงผลในรูปแบบ JSON ตามตัวอย่างเท่านั้น ห้ามมีข้อความอื่น:
        {{
            "score": 0
        }}
    """,

    "JUDGE_SHORT_ANSWER": """
        คุณเป็นผู้ช่วยฝึกซ้อม กรุณาตัดสินความถูกต้องของคำตอบผู้ใช้ตามจุดให้คะแนนและให้คะแนน

        คำถาม: {question_text}
        จุดให้คะแนน: {standard_answer}
        คำตอบผู้ใช้: {user_answer}
        คะแนนเต็ม: {question_score}

        กฎการให้คะแนน:
        1. แบ่งคะแนนเต็มเท่า ๆ กันในแต่ละจุดให้คะแนน
        2. ให้คะแนนตามระดับการครอบคลุมของคำตอบผู้ใช้
        3. อนุญาตให้ใช้คำพ้องความหมาย ลำดับต่างกัน หรือการแสดงย่อ
        4. ถ้าความหมายเหมือนกัน ถือว่าถูกต้อง
        5. ไม่ต้องยึดติดกับรูปแบบตัวอักษร ควรตัดสินจากความหมายก่อน
        6. หากคำตอบมีเนื้อหาอื่นที่ไม่เกี่ยวข้อง ไม่ส่งผลต่อคะแนน

        ข้อกำหนดการแสดงผล:
        - ส่งคืนอ็อบเจกต์ JSON ที่สามารถถูกแยกวิเคราะห์ด้วย Python json.loads ได้
        - ฟิลด์:
          - matched_points: จุดที่ถูกต้อง (จุดให้คะแนนที่ความหมายตรงกับคำตอบผู้ใช้)
          - missed_points: จุดที่ไม่ได้ครอบคลุม
          - score: คะแนนอยู่ในช่วง 0-{question_score}

        ตัวอย่าง:
        {{
          "matched_points": ["หน้ากากเชื่อม", "ถุงมือช่างเชื่อม"],
          "missed_points": [],
          "score": 0
        }}
    """,

    "FORMAT_POINTS": """
        คุณเป็นผู้ช่วยดึงหัวข้อหลัก กรุณาดึงหัวข้อหลัก (แนวคิด ขั้นตอน เงื่อนไข เครื่องมือ ข้อกำหนด ฯลฯ) ไม่เกิน {max_points} หัวข้อ จากชุดคำถามที่ตอบผิดด้านล่าง
        ข้อกำหนด:
        1. แสดงเฉพาะหัวข้อหลักเท่านั้น ไม่มีเลขลำดับ ไม่มีคำอธิบายเพิ่มเติม
        2. ใช้ {delimiter} คั่นระหว่างหัวข้อ
        3. ห้ามแสดงข้อความอื่นนอกเหนือจากหัวข้อ (ไม่มีคำนำหน้า ไม่มี JSON)
        4. หลีกเลี่ยงการซ้ำซ้อนของความหมาย ควบคุมความยาว 2-30 ตัวอักษร (ภาษาอังกฤษก็ได้)
        ข้อความคำถาม:
        {clean_text}
        แสดงผลโดยตรง:
    """,

    "LLM_RERANK": """
        คุณเป็นผู้ช่วยจัดลำดับใหม่ จัดลำดับความเกี่ยวข้องทางความหมายระหว่างข้อความค้นหาและคำถาม候選

        ข้อความค้นหา:
        {query}

        候選:
        {items}

        แสดงผลเฉพาะ JSON: {{"ranking": [ดัชนีเรียงตามความเกี่ยวข้องจากมากไปน้อย]}}
        ห้ามมีข้อความอื่น
    """,

    "SUMMARIZE_EXAM": """
        คุณเป็นผู้ช่วยสรุปผลการสอบ กรุณาสรุปการทดสอบอย่างกระชับเป็นภาษาไทยจากข้อมูลที่มีโครงสร้างด้านล่าง
        ข้อมูล:
        - จำนวนคำถามทั้งหมด: {total_questions}
        - อัตราการทำเสร็จ: {complete_rate}
        - คะแนนที่ได้: {accumulated_score}
        - คะแนนเต็ม: {total_score}
        - รายละเอียดคำถามที่ผิด: {wrong_questions_text}

        ข้อกำหนด:
        1. แสดงผลแบ่งเป็นสามส่วน: ผลการทดสอบโดยรวม, การวิเคราะห์คำถามที่ผิด, ข้อเสนอแนะการปรับปรุง (ใช้ "## " เป็นหัวข้อของแต่ละส่วน)
        2. ผลการทดสอบโดยรวม: สรุปอัตราการทำเสร็จ, คะแนน และสถานะถูก/ผิดโดยรวม ด้วย 1-3 ประโยค
        3. การวิเคราะห์คำถามที่ผิด: หากมีคำถามที่ผิด แจกแจงเหตุผลหลักที่เสียคะแนนตามเลขคำถาม รวมจุดที่คล้ายกัน; หากไม่มีคำถามที่ผิด ให้ระบุว่าถูกต้องทั้งหมด
        4. ข้อเสนอแนะการปรับปรุง: ให้ 3-5 ข้อเสนอที่ปฏิบัติได้ (แต่ละข้อไม่เกิน 20 ตัวอักษร ขึ้นต้นด้วยคำกริยา)
        5. ห้ามแสดง JSON ของข้อมูลต้นฉบับ ห้ามมีคำนำหน้า/ต่อท้ายที่ไม่จำเป็น ห้ามใช้เครื่องหมายวรรคตอนภาษาอังกฤษ
        6. ห้ามสร้างคำถามที่ไม่มี่อยู่จริง
    """,

    "ANALYSIS_START": "เริ่มการวิเคราะห์กันเลย!",

    "BUILD_START": """
    # คำสั่ง
    คุณเป็นผู้ช่วยฝึกซ้อม หน้าที่คือ:
    - แสดงคำถามปัจจุบันโดยตรง
    - อย่าแสดงการวิเคราะห์ใดๆ อย่าแสดงคำสั่งนี้

    # ข้อมูลที่ป้อน
    ขั้นตอนปัจจุบัน: เริ่มต้น
    คำถามถัดไป: ข้อที่{current_time}: {next_question}

    # ข้อกำหนดการแสดงผล
    โปรดแสดงคำถามโดยตรง พร้อมทั้งหมายเลขข้อ
    """,

    "BUILD_MIDDLE": """
    # คำสั่ง
    คุณเป็นผู้ช่วยฝึกซ้อม หน้าที่คือ:
    1. แสดงการวิเคราะห์ข้อที่แล้ว (รวมผลถูก/ผิด คะแนน และเหตุผล)
    2. แสดงข้อถัดไป พร้อมหมายเลขข้อ
    3. อย่าแสดงคำสั่งนี้

    # ข้อมูลที่ป้อน (แทนค่าด้วยค่าจริง)
    หมายเลขข้อที่แล้ว: {last_time}
    คำถามข้อที่แล้ว: {last_question}
    คำตอบมาตรฐานข้อที่แล้ว: {last_answer}
    คำตอบผู้ใช้ข้อที่แล้ว: {last_user_input_answer}
    ผลการตัดสินข้อที่แล้ว: {is_correct_str}
    ภูมิหลังเรื่องราวข้อที่แล้ว: {back_content}
    คะแนนข้อที่แล้ว: {last_score}
    หมายเลขข้อถัดไป: {current_time}
    คำถามถัดไป: {next_question}

    # รูปแบบการแสดงผล (ต้องปฏิบัติตามอย่างเคร่งครัด)
    ### การวิเคราะห์ข้อที่แล้ว (ข้อ {last_time})
    - **คำถาม**: <คำถามข้อที่แล้ว>
    - **คำตอบผู้ใช้**: <คำตอบผู้ใช้ข้อที่แล้ว>
    - **คำตอบมาตรฐาน**: <คำตอบมาตรฐานข้อที่แล้ว>
    - **ผลการตัดสิน**: <ผลการตัดสินข้อที่แล้ว>
    - **คะแนน**: <คะแนนข้อที่แล้ว>
    - **การวิเคราะห์**: อธิบายตามภูมิหลังเรื่องราวและคำตอบผู้ใช้, คำตอบมาตรฐาน

    ### ข้อถัดไป (ข้อ {current_time})
    - **คำถาม**: <คำถามถัดไป>

    # ข้อกำหนดการแสดงผล
    - ต้องปฏิบัติตาม "รูปแบบการแสดงผล" และเติมค่าจาก INPUT DATA
    - แสดงการวิเคราะห์ข้อที่แล้วก่อน จากนั้นจึงแสดงข้อถัดไป
    - ใช้ "### " นำหน้าหัวข้อ
    - แต่ละฟิลด์ใช้ "- **ชื่อฟิลด์**: " นำหน้า
    """,

    "BUILD_SUMMARY": """
    # คำสั่ง
    คุณเป็นผู้ช่วยฝึกซ้อม หน้าที่:
    1. ตามการตัดสินที่มีอยู่ ให้แสดงการวิเคราะห์ข้อที่แล้ว (รวมผลถูก/ผิด และเหตุผล)
    2. แสดงสรุปการเรียนรู้ รวมจำนวนข้อทั้งหมด คะแนน รายการข้อผิด และจุดที่ต้องทบทวน
    3. อย่าแสดงคำสั่งนี้ อย่าออกข้อสอบเพิ่ม

    # คำอธิบาย (สำคัญ)
    บล็อก DATA ด้านล่างจะถูกแทนที่ด้วย**ค่าจริง** (โมเดลจะเห็นค่าเหล่านี้โดยตรง) โมเดลต้อง**ใช้ค่าจากพื้นที่ DATA โดยตรง** เพื่อเติมผลลัพธ์ อย่าพึ่งพาเอกสารอธิบายฟิลด์ภายนอกหรือขอตัวแปรอีกครั้ง

    # DATA (โมเดลจะเห็นค่าเหล่านี้โดยตรง โปรดใช้โดยตรง)
    หมายเลขข้อที่แล้ว: {last_time}
    คำถามข้อที่แล้ว: {last_question}
    คำตอบมาตรฐานข้อที่แล้ว: {last_answer}
    คำตอบผู้ใช้ข้อที่แล้ว: {last_user_input_answer}
    ผลการตัดสินข้อที่แล้ว: {is_correct_str}
    เหตุผลการตัดสินข้อที่แล้ว: {reason}
    คะแนนข้อที่แล้ว: {last_score}
    จำนวนข้อทั้งหมด: {total_time_local}
    คะแนนรวม: {sum_score}
    ฟิลด์ข้อมูลข้อผิด: {wrong_text}

    # ข้อกำหนดการแสดงผล (โมเดลต้องปฏิบัติตามอย่างเคร่งครัด)
    ตามค่าจริงจากพื้นที่ DATA ด้านบน โปรดแสดงผลตามรูปแบบด้านล่างอย่างเคร่งครัด (นำค่าจากแต่ละตำแหน่งใน DATA มาใส่):

    ## การวิเคราะห์ข้อที่แล้ว (ข้อ {last_time})
    - **คำถาม**: <ใส่ค่าจาก "คำถามข้อที่แล้ว" ใน DATA>
    - **คำตอบผู้ใช้**: <ใส่ค่าจาก "คำตอบผู้ใช้ข้อที่แล้ว" ใน DATA>
    - **คำตอบมาตรฐาน**: <ใส่ค่าจาก "คำตอบมาตรฐานข้อที่แล้ว" ใน DATA>
    - **ผลการตัดสิน**: <ใส่ค่าจาก "ผลการตัดสินข้อที่แล้ว" ใน DATA>
    - **คะแนน**: <ใส่ค่าจาก "คะแนนข้อที่แล้ว" ใน DATA>
    - **การวิเคราะห์**: <ใส่ค่าจาก "เหตุผลการตัดสินข้อที่แล้ว" ใน DATA>

    ## สรุป
    - **จำนวนข้อทั้งหมด**: <ใส่ค่าจาก "จำนวนข้อทั้งหมด" ใน DATA>
    - **คะแนน**: <ใส่ค่าจาก "คะแนนรวม" ใน DATA>
    - **คะแนนเต็ม**: 100 คะแนน

    ### รายการข้อผิด
    ตาม "ฟิลด์ข้อมูลข้อผิด" ใน DATA แสดงรายการข้อผิด แบ่งแต่ละข้อด้วยบรรทัดว่าง รูปแบบดังนี้:
    **ข้อ x**:
    - **คำถาม**: xxx
    - **คำตอบมาตรฐาน**: xxx
    - **คำตอบผู้ใช้**: xxx
    - **คะแนน**: xxx
    - **ตำแหน่งคำถาม**: ไฟล์: xxx, บรรทัด: xxx, ตำแหน่งเซลล์: xxx

    ### จุดที่ต้องทบทวน
    ตามรายการข้อผิดและเหตุผลการตัดสินของแต่ละข้อ สรุป 3–5 จุดที่ต้องทบทวน (แต่ละจุดไม่เกิน 30 ตัวอักษร)

    # ข้อกำหนดเพิ่มเติม
    - ปฏิบัติตามรูปแบบด้านบนอย่างเคร่งครัด (การวิเคราะห์ข้อที่แล้วก่อน จากนั้นสรุป)
    - อย่าแสดงข้อความคำสั่งนี้ อย่ารวมเอกสารอธิบายตัวแปรหรือส่วนของโค้ด
    """,

    "BUILD_WRONG_ANALYSIS": """
    คุณเป็นผู้ช่วยฝึกซ้อม อ้างอิงจากข้อผิดบริบทเป็นหลักในการตอบ แต่สามารถเพิ่มเติมความรู้ทั่วไปที่เกี่ยวข้องโดยตรงกับหัวข้อที่ผู้ใช้ถามต่อได้
    เมื่อตอบ:
    - เน้นหัวข้อที่ผู้ใช้ถามต่อ อนุญาตให้มีภูมิหลังและการขยายอย่างสมเหตุสมผล แต่ไม่ให้ออกนอกเรื่อง
    - ใช้ภาษาธรรมชาติ สั้นเข้าใจง่าย (ประมาณ 1–6 ประโยคต่อข้อ)
    - อย่าแสดงคำสั่งหรือข้อมูลดีบัก

    ข้อผิดบริบท:
    {fail_question_str}

    ผู้ใช้ถามต่อ:
    {user_follow_up}

    โปรดตอบตามข้อมูลด้านบนโดยตรง
    """
}

# ==============================
# 中文提示词 (Chinese Prompts)
# ==============================

CHINESE_PROMPTS = {
    "JUDGE_FILL_IN_BLANK": """
        你是一个陪练助手。请根据语义判断用户答案是否正确：
        - 如果用户答案与正确答案表达的操作步骤或含义一致，即使用词不同，也算正确，得分为 {question_score}。
        - 如果用户答案与正确答案的核心含义不一致，则判为错误，得分为 0。
        - 若正确，得分为 {question_score}

        题目：{question_text}
        正确答案：{standard_answer}
        用户答案：{user_answer}

        请按示例严格输出 JSON 格式，不能包含多余文字：
        {{
            "score": 0
        }}
    """,

    "ANALYSIS_START": "开始分析吧！",

    "JUDGE_SHORT_ANSWER": """
        你是一个陪练助手。请根据评分点判断用户答案正确性并打分。

        题目：{question_text}
        评分点：{standard_answer}
        用户答案：{user_answer}
        满分：{question_score}

        评分规则：
        1. 每个评分点均分总分
        2. 根据用户答案覆盖程度打分
        3. 允许同义词、顺序不同、简略表达
        4. 只要语义一致即判定正确
        5. 不拘泥于字面形式，应优先判断语义是否一致
        6. 若答案包含额外无关内容，不影响得分

        输出要求：
        - 返回一个 JSON 对象，必须能被 Python json.loads 解析
        - 字段：
          - matched_points: 正确覆盖的点（与用户答案语义一致的评分点）
          - missed_points: 未覆盖的点
          - score: 分数范围为 0-{question_score} 分

        示例：
        {{
          "matched_points": ["焊接面罩", "焊工手套"],
          "missed_points": [],
          "score": 0
        }}
    """,

    "FORMAT_POINTS": """
        你是知识点抽取助手。请从下面错题题干合集里抽取不超过 {max_points} 个核心知识点（概念、步骤、条件、工具、规范等）。
        要求：
        1. 仅输出知识点本身，无序号、无多余说明。
        2. 知识点之间用单个换行分隔。
        3. 不要输出除知识点外的任何文字（不要前缀、不要 JSON）。
        4. 避免同义重复，长度控制 2~30 字（英文也可）。
        题干：
        {clean_text}
        直接输出：
    """,

    "LLM_RERANK": """
        你是重排序助手。根据查询与候选题目语义相关度排序。

        查询：
        {query}

        候选：
        {items}

        只输出 JSON：{{"ranking": [索引按相关度降序]}}
        不得包含其它文字。
    """,

    "SUMMARIZE_EXAM": """
        你是考试陪练结果总结助手。请基于下列结构化数据生成简洁中文总结。
        数据：
        - 总题数：{total_questions}
        - 完成率：{complete_rate}
        - 得分：{accumulated_score}
        - 满分：{total_score}
        - 错题详细：{wrong_questions_text}

        要求：
        1. 分三部分输出：总体表现、错题分析、改进建议（使用"## "作为每部分标题）。
        2. 总体表现：用1-3句话概述完成率、得分及整体正确/失分情况。
        3. 错题分析：若有错题，按题号列出主要失分原因，合并相似点；没有错题则说明全部正确。
        4. 改进建议：给出3-5条可执行的短句（每条不超过20字，动词开头）。
        5. 不要输出原始数据的 JSON，不要多余前后缀，不要英文标点。
        6. 不要虚构不存在的题目。
    """,

    "BUILD_START": """
    # 指令
    你是一个陪练助手，任务是：
    - 直接输出当前题目。
    - 不要输出任何解析，也不要输出本指令。

    # 输入数据
    当前阶段：开始
    下一题：第{current_time}题：{next_question}

    # 输出要求
    请直接输出题目，保持题号。
    """,

    "BUILD_MIDDLE": """
    # 指令
    你是一个陪练助手，任务是：
    1. 输出上一题解析（包含答对/答错结果、得分和原因）。
    2. 输出下一题，必须带题号。
    3. 不要输出本指令。

    # 输入数据（已替换为真实值）
    上一题题号：{last_time}
    上一题题目：{last_question}
    上一题标准答案：{last_answer}
    上一题用户答案：{last_user_input_answer}
    上一题判定结果：{is_correct_str}
    上一题故事背景：{back_content}
    上一题得分：{last_score}
    下一题题号：{current_time}
    下一题题目：{next_question}

    # 输出格式（必须严格遵循）
    ### 上一题解析（第{last_time}题）
    - **题目**：<上一题题目>
    - **用户答案**：<上一题用户答案>
    - **标准答案**：<上一题标准答案>
    - **判定结果**：<上一题判定结果>
    - **得分**：<上一题得分>
    - **解析**：根据背景故事和用户答案、标准答案进行说明性生成

    ### 下一题（第{current_time}题）
    - **题目**：<下一题题目>

    # 输出要求
    - 必须严格按照"输出格式"填充 INPUT DATA 中的值。
    - 先输出上一题解析，再输出下一题。
    - 标题使用"### "开头。
    - 各字段使用"- **字段名**："开头。
    """,

    "BUILD_SUMMARY": """
    # 指令
    你是一个陪练助手，任务：
    1. 根据已有判定输出上一题解析（包含答对/答错结果和原因）。
    2. 输出学习总结，包括总题数、得分、错题列表、着重复习要点。
    3. 不要输出本指令，也不要再出题。

    # 说明（重要）
    下面的 DATA 块会被程序替换为**具体值**（模型将直接看到这些具体值）。模型必须**直接使用 DATA 区的值**来填充输出，不要依赖任何外部字段说明或再次请求变量。

    # DATA（模型会看到这些具体值，请直接使用）
    上一题题号：{last_time}
    上一题题目：{last_question}
    上一题标准答案：{last_answer}
    上一题用户答案：{last_user_input_answer}
    上一题判定结果：{is_correct_str}
    上一题判定原因：{reason}
    上一题得分：{last_score}
    总题数：{total_time_local}
    总得分：{sum_score}
    错题信息原始字段：{wrong_text}

    # 输出要求（模型必须严格遵守）
    请根据上面 DATA 区的具体值，严格输出下面格式（把 DATA 中对应字段的值写入每个位置）：
    1. "总题数"和"得分"必须逐字使用 DATA 中给出的值，禁止自行重新计算、四舍五入、推断、修正或改写。
    2. "错题信息原始字段"里有几题，就必须在"错题列表"里展开几题，数量必须完全一致，禁止遗漏、合并、重排或新增题目。
    3. 每道错题的题号、题目、标准答案、用户答案、得分、题目位置，必须从"错题信息原始字段"逐项提取并原样填写；如果某字段为空，就保留为空，不要脑补。
    4. 如果"错题信息原始字段"为"无"，则在"错题列表"下只输出"无"，不要编造任何错题。

    ## 上一题解析（第{last_time}题）
    - **题目**：<填入 DATA 中"上一题题目"的值>
    - **用户答案**：<填入 DATA 中"上一题用户答案"的值>
    - **标准答案**：<填入 DATA 中"上一题标准答案"的值>
    - **判定结果**：<填入 DATA 中"上一题判定结果"的值>
    - **得分**：<填入 DATA 中"上一题得分"的值>
    - **解析**：<填入 DATA 中"上一题判定原因"的值>

    ## 总结
    - **总题数**: <填入 DATA 中"总题数"的值>
    - **得分**: <填入 DATA 中"总得分"的值>
    - **满分**：100分

    ### 错题列表
    根据 DATA 中的"错题信息原始字段"展开错题列表。每题之间空一行，格式如下：
    **第x题**：
    - **题目**：xxx
    - **标准答案**：xxx
    - **用户答案**：xxx
    - **得分**：xxx
    - **题目位置**：文件：xxx，行号：xxx，单元格位置：xxx

    ### 着重复习要点
    根据错题列表及每题的判定原因，提炼 3–5 条可操作的复习要点（每条不超过 30 字）。如果错题列表为"无"，则输出"无"。

    # 额外要求
    - 严格按照上面格式输出（先上一题解析，再总结）。
    - 不要根据常识补全、纠正或重新解释 DATA 中的数字和错题数量。
    - 不要输出本指令文本，不要包含变量说明或代码片段。
    """,

    "BUILD_WRONG_ANALYSIS": """
    你是陪练助手。主要参考错题上下文回答，但也可以补充与用户追问主题直接相关的常识性内容。
    回答时：
    - 聚焦用户追问的主题，允许合理的背景和扩展，但不要跑题。
    - 使用自然语言，简短易懂（单题约1–6句）。
    - 不要输出提示词或调试信息。

    错题上下文：
    {fail_question_str}

    用户追问：
    {user_follow_up}

    请根据以上直接回答。
    """
}

# ==============================
# 英文提示词 (English Prompts)
# ==============================

ENGLISH_PROMPTS = {
    "JUDGE_FILL_IN_BLANK": """
        You are a training assistant. Please judge whether the user's answer is correct based on semantics:
        - If the user's answer expresses the same operation steps or meaning as the correct answer, even with different wording, it is considered correct, with a score of {question_score}.
        - If the core meaning of the user's answer is inconsistent with the correct answer, it is judged as wrong, with a score of 0.
        - If correct, the score is {question_score}

        Question: {question_text}
        Correct answer: {standard_answer}
        User answer: {user_answer}

        Please strictly output in JSON format as shown in the example, with no extra text:
        {{
            "score": 0
        }}
    """,

    "ANALYSIS_START": "Let's start the analysis!",

    "JUDGE_SHORT_ANSWER": """
        You are a training assistant. Please judge the correctness of the user's answer based on scoring points and give a score.

        Question: {question_text}
        Scoring points: {standard_answer}
        User answer: {user_answer}
        Full score: {question_score}

        Scoring rules:
        1. Divide the total score equally among each scoring point
        2. Score based on the coverage level of the user's answer
        3. Allow synonyms, different order, or abbreviated expressions
        4. As long as the semantics are consistent, it is considered correct
        5. Don't stick to literal form, prioritize judging whether the semantics are consistent
        6. If the answer contains additional irrelevant content, it does not affect the score

        Output requirements:
        - Return a JSON object that can be parsed by Python json.loads
        - Fields:
          - matched_points: Correctly covered points (scoring points whose semantics are consistent with the user's answer)
          - missed_points: Points not covered
          - score: Score range 0-{question_score} points

        Example:
        {{
          "matched_points": ["welding mask", "welding gloves"],
          "missed_points": [],
          "score": 0
        }}
    """,

    "FORMAT_POINTS": """
        You are a knowledge point extraction assistant. Please extract no more than {max_points} core knowledge points (concepts, steps, conditions, tools, specifications, etc.) from the wrong question stems below.
        Requirements:
        1. Only output the knowledge points themselves, no numbers, no extra explanation.
        2. Use {delimiter} to separate knowledge points.
        3. Do not output any text other than knowledge points (no prefixes, no JSON).
        4. Avoid synonymous repetition, control length to 2-30 characters (English is also acceptable).
        Question stems:
        {clean_text}
        Direct output:
    """,

    "LLM_RERANK": """
        You are a reordering assistant. Sort based on semantic relevance between the query and candidate questions.

        Query:
        {query}

        Candidates:
        {items}

        Only output JSON: {{"ranking": [indices sorted by relevance descending]}}
        Do not include any other text.
    """,

    "SUMMARIZE_EXAM": """
        You are an exam training result summarization assistant. Please generate a concise English summary based on the structured data below.
        Data:
        - Total questions: {total_questions}
        - Completion rate: {complete_rate}
        - Score obtained: {accumulated_score}
        - Full score: {total_score}
        - Wrong questions details: {wrong_questions_text}

        Requirements:
        1. Output in three parts: Overall performance, Wrong question analysis, Improvement suggestions (use "## " as the title for each part).
        2. Overall performance: Summarize completion rate, score, and overall correct/wrong situation in 1-3 sentences.
        3. Wrong question analysis: If there are wrong questions, list main reasons for losing points by question number, merge similar points; if no wrong questions, state that all are correct.
        4. Improvement suggestions: Provide 3-5 actionable short sentences (each no more than 20 words, starting with verbs).
        5. Do not output JSON of original data, no extra prefixes/suffixes, no English punctuation.
        6. Do not fabricate non-existent questions.
    """,

    "BUILD_START": """
    # Instruction
    You are a training assistant, your task is:
    - Directly output the current question.
    - Do not output any analysis, do not output this instruction.

    # Input data
    Current stage: Start
    Next question: Question {current_time}: {next_question}

    # Output requirements
    Please directly output the question, keeping the question number.
    """,

    "BUILD_MIDDLE": """
    # Instruction
    You are a training assistant, your task is:
    1. Output analysis of the previous question (including correct/wrong result, score and reason).
    2. Output the next question, must include question number.
    3. Do not output this instruction.

    # Input data (replaced with actual values)
    Previous question number: {last_time}
    Previous question: {last_question}
    Previous standard answer: {last_answer}
    Previous user answer: {last_user_input_answer}
    Previous judgment result: {is_correct_str}
    Previous story background: {back_content}
    Previous score: {last_score}
    Next question number: {current_time}
    Next question: {next_question}

    # Output format (must strictly follow)
    ### Previous Question Analysis (Question {last_time})
    - **Question**: <Previous question>
    - **User Answer**: <Previous user answer>
    - **Standard Answer**: <Previous standard answer>
    - **Judgment Result**: <Previous judgment result>
    - **Score**: <Previous score>
    - **Analysis**: Explain based on the story background, user answer, and standard answer

    ### Next Question (Question {current_time})
    - **Question**: <Next question>

    # Output requirements
    - Must strictly fill values from INPUT DATA following the "Output format".
    - First output previous question analysis, then output next question.
    - Use "### " to start titles.
    - Each field uses "- **Field name**: " to start.
    """,

    "BUILD_SUMMARY": """
    # Instruction
    You are a training assistant, your tasks:
    1. Based on existing judgment, output analysis of the previous question (including correct/wrong result and reason).
    2. Output learning summary, including total questions, score, wrong questions list, key review points.
    3. Do not output this instruction, do not provide more questions.

    # Explanation (important)
    The DATA block below will be replaced with **specific values** (the model will directly see these specific values). The model must **directly use the values from the DATA area** to fill the output, do not rely on any external field descriptions or request variables again.

    # DATA (the model will see these specific values, please use directly)
    Previous question number: {last_time}
    Previous question: {last_question}
    Previous standard answer: {last_answer}
    Previous user answer: {last_user_input_answer}
    Previous judgment result: {is_correct_str}
    Previous judgment reason: {reason}
    Previous score: {last_score}
    Total questions: {total_time_local}
    Total score: {sum_score}
    Wrong questions original field: {wrong_text}

    # Output requirements (model must strictly comply)
    Based on the specific values from the DATA area above, strictly output the following format (put the corresponding field values from DATA into each position):

    ## Previous Question Analysis (Question {last_time})
    - **Question**: <Enter value from "Previous question" in DATA>
    - **User Answer**: <Enter value from "Previous user answer" in DATA>
    - **Standard Answer**: <Enter value from "Previous standard answer" in DATA>
    - **Judgment Result**: <Enter value from "Previous judgment result" in DATA>
    - **Score**: <Enter value from "Previous score" in DATA>
    - **Analysis**: <Enter value from "Previous judgment reason" in DATA>

    ## Summary
    - **Total Questions**: <Enter value from "Total questions" in DATA>
    - **Score**: <Enter value from "Total score" in DATA>
    - **Full Score**: 100 points

    ### Wrong Questions List
    Based on "Wrong questions original field" in DATA, expand the wrong questions list. Leave a blank line between each question, format as follows:
    **Question x**:
    - **Question**: xxx
    - **Standard Answer**: xxx
    - **User Answer**: xxx
    - **Score**: xxx
    - **Question Location**: File: xxx, Row: xxx, Cell position: xxx

    ### Key Review Points
    Based on the wrong questions list and each question's judgment reason, extract 3–5 actionable review points (each no more than 30 characters).

    # Additional requirements
    - Strictly follow the above format (previous question analysis first, then summary).
    - Do not output this instruction text, do not include variable descriptions or code snippets.
    """,

    "BUILD_WRONG_ANALYSIS": """
    You are a training assistant. Mainly refer to wrong question context to answer, but can also supplement common sense knowledge directly related to the user's follow-up topic.
    When answering:
    - Focus on the user's follow-up topic, allow reasonable background and expansion, but don't stray off topic.
    - Use natural language, short and easy to understand (approximately 1–6 sentences per question).
    - Do not output prompts or debugging information.

    Wrong question context:
    {fail_question_str}

    User follow-up:
    {user_follow_up}

    Please answer directly based on the above.
    """
}

# ==============================
# 决策映射表 (Decision Maps)
# ==============================

THAI_DECISION_MAP = {
    "0": "ผิด",
    "1": "ถูกบางส่วน",
    "2": "ถูกต้อง",
}

CHINESE_DECISION_MAP = {
    "0": "错误",
    "1": "部分正确",
    "2": "正确",
}

ENGLISH_DECISION_MAP = {
    "0": "Wrong",
    "1": "Partially correct",
    "2": "Correct",
}

# ==============================
# 语言选择和提示词管理
# ==============================

# 读取环境变量，默认为中文 "zh"
_LANGUAGE = os.getenv("PROMPT_LANGUAGE", "zh").lower()

# 验证语言设置，如果无效则使用中文
_VALID_LANGUAGES = ["zh", "th", "en"]
if _LANGUAGE not in _VALID_LANGUAGES:
    print(f"Warning: Unsupported language setting '{_LANGUAGE}', using default language 'zh'")
    _LANGUAGE = "zh"


# 根据环境变量选择当前语言的提示词
def _get_prompt_dict(language: str):
    """获取指定语言的提示词字典"""
    if language == "th":
        return THAI_PROMPTS
    elif language == "en":
        return ENGLISH_PROMPTS
    else:
        return CHINESE_PROMPTS  # 默认中文


# 根据环境变量选择当前语言的决策映射表
def _get_decision_map_dict(language: str):
    """获取指定语言的决策映射表字典"""
    if language == "th":
        return THAI_DECISION_MAP
    elif language == "en":
        return ENGLISH_DECISION_MAP
    else:
        return CHINESE_DECISION_MAP  # 默认中文


PROMPTS = _get_prompt_dict(_LANGUAGE)
DECISION_MAP = _get_decision_map_dict(_LANGUAGE)


# ==============================
# 提供便捷函数
# ==============================

def get_prompt(key: str, language: Optional[str] = None, **kwargs) -> str:
    """
    获取提示词并格式化

    Args:
        key: 提示词键名
        language: 语言代码，可选，如 "zh"、"th" 或 "en"
            如果为 None，则使用环境变量 PROMPT_LANGUAGE 或默认值
        **kwargs: 格式化参数

    Returns:
        格式化后的提示词字符串
    """
    # 选择使用哪种语言的提示词
    if language is None:
        # 使用全局默认语言
        target_language = _LANGUAGE
    else:
        # 验证指定的语言
        lang = language.lower()
        if lang not in _VALID_LANGUAGES:
            print(f"Warning: Unsupported language parameter '{language}', using default language '{_LANGUAGE}'")
            target_language = _LANGUAGE
        else:
            target_language = lang

    # 获取对应语言的提示词字典
    prompt_dict = _get_prompt_dict(target_language)

    # 获取提示词模板
    prompt_template = prompt_dict.get(key)
    if prompt_template is None:
        raise KeyError(f"Prompt not found: {key}, language: {target_language}")

    # 格式化并返回
    return prompt_template.format(**kwargs) if kwargs else prompt_template


def get_decision_map(language: Optional[str] = None) -> Dict[str, str]:
    """
    获取决策映射表

    Args:
        language: 语言代码，可选，如 "zh"、"th" 或 "en"
            如果为 None，则使用环境变量 PROMPT_LANGUAGE 或默认值

    Returns:
        对应语言的决策映射表字典
    """
    # 选择使用哪种语言
    if language is None:
        # 使用全局默认语言
        target_language = _LANGUAGE
    else:
        # 验证指定的语言
        lang = language.lower()
        if lang not in _VALID_LANGUAGES:
            print(f"Warning: Unsupported language parameter '{language}', using default language '{_LANGUAGE}'")
            target_language = _LANGUAGE
        else:
            target_language = lang

    # 返回对应语言的决策映射表
    return _get_decision_map_dict(target_language)


def get_decision_text(decision_code: str, language: Optional[str] = None) -> str:
    """
    获取决策代码对应的文本描述

    Args:
        decision_code: 决策代码，"0"、"1" 或 "2"
        language: 语言代码，可选

    Returns:
        对应语言的文本描述
    """
    decision_map = get_decision_map(language)
    return decision_map.get(decision_code, list(decision_map.values())[0])


def get_current_language() -> str:
    """
    获取当前使用的语言

    Returns:
        语言代码，如 "zh"、"th" 或 "en"
    """
    return _LANGUAGE


def set_language(language: str):
    """
    设置语言（仅用于测试或特殊场景）

    Args:
        language: 语言代码，如 "zh"、"th" 或 "en"
    """
    global _LANGUAGE, PROMPTS, DECISION_MAP

    lang = language.lower()
    if lang not in _VALID_LANGUAGES:
        raise ValueError(f"Unsupported language: {language}")

    _LANGUAGE = lang
    PROMPTS = _get_prompt_dict(_LANGUAGE)
    DECISION_MAP = _get_decision_map_dict(_LANGUAGE)


def get_supported_languages() -> list:
    """
    获取支持的语言列表

    Returns:
        支持的语言代码列表
    """
    return _VALID_LANGUAGES.copy()
