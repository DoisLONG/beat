# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

GET_FILE_LANG_PROMPT_ZH = """
You are a linguistic expert. 
        Analyze the provided content and identify the DOMINANT language (the one used in the majority of rows/sentences).

        Return ONLY a JSON object: {{"language": "code"}}

        Rules:
        - If the content is a mix, count the number of rows for each language. 
        - Technical IDs (like 'TTPOS-211') and numbers should be ignored.
        - If more than 70% of the descriptive text is English, return "en".
        - If the majority is Thai, return "th".
        - Only return "zh" if Chinese is the primary descriptive language.

        Allowed codes: "zh", "th", "en"
        Default: "zh" (if unsure or exactly 50/50 mix)

        Content: 
        {sample_content}
"""


GET_EXCEL_HEAD_AND_DATA_PROMPT_ZH = """
你是一名专业的数据分析与表格结构识别专家。输入为 Excel 文件前若干行的内容预览 {preview_text}，可能含有复杂的 多行表头、多列合并单元格、字段跨行跨列合并、以及空白单元格。

你的任务是：
从这些预览内容中准确识别最终的列头（Header）列表，并输出最终的 heads 数组（按视觉顺序）。

### 
表头识别规则（修正版核心逻辑）
    若上层表头跨多列，但这些列在下一行具有各自的子标题，则最终列头只能使用子标题，不得把上层标题与子标题拼接。
    示例：
    上层：作业标准1-文字说明（跨 4 列）
    下层：具体做什么(动作分解)，做到什么程度(数据定标)，特别风险，特别风险管控
    → 最终输出必须是 4 个子标题，而不是上层标题与子标题的合并。
    仅在一个列头区域纵向合并（上下一列都是同一列标题）时，才把多行文本拼接。
    即：
    若上层文本合并了多行，但只对应一个最终列
    → 才拼接成 "A\nB"。
    若上层仅是结构分组，不应进入最终 heads。
    最终 heads 必须与实际数据行的列数一致。
###

请严格返回以下 JSON 格式：
{{
  "heads": ["表头1", "表头2", "表头3", ...],
  "start_row": <int>,
  "end_row": <int>
}}
其中
heads：从左到右所有最终列头文本。若列头跨多行，则将多行文本 合并为一个字符串，按出现顺序用 \n 连接。若列头因合并单元格缺失，允许推断，并必须确保 heads 数组完整。
start_row、end_row：Excel 中所有表头区域所覆盖的起始/结束行（从 1 开始，依据预览内容推断）。
"""

GET_EXCEL_HEAD_AND_DATA_PROMPT_TH = """
คุณคือผู้เชี่ยวชาญด้านการวิเคราะห์ข้อมูลและการระบุโครงสร้างตาราง (Table Structure Recognition) 
ข้อมูลนำเข้าคือตัวอย่างเนื้อหาจากไฟล์ Excel: {preview_text} ซึ่งอาจมีหัวตารางหลายชั้น (Multi-line header), 
การผสานเซลล์ (Merged cells), และเซลล์ว่าง

ภารกิจของคุณคือ:
ระบุรายการหัวตาราง (Heads) สุดท้ายให้ถูกต้องจากเนื้อหาพรีวิวนี้ และส่งออกเป็นอาร์เรย์ heads (ตามลำดับที่ปรากฏ)

### กฎการระบุหัวตาราง (Rules):
1. หากหัวตารางด้านบน (Upper Header) ครอบคลุมหลายคอลัมน์ แต่คอลัมน์เหล่านั้นมี "หัวข้อย่อย (Sub-titles)" ในแถวถัดไป 
   ให้ใช้เฉพาะหัวข้อย่อยเป็นชื่อหัวตารางเท่านั้น **ห้าม** นำหัวข้อย่อยไปต่อท้ายหัวข้อใหญ่
   ตัวอย่าง:
   ชั้นบน: "มาตรฐานการทำงาน (ข้อความ)" (ครอบคลุม 4 คอลัมน์)
   ชั้นล่าง: "ขั้นตอนการทำงาน", "เกณฑ์มาตรฐาน", "ความเสี่ยง", "การควบคุม"
   → ผลลัพธ์ต้องเป็นหัวตาราง 4 ตัวแยกกัน ไม่ใช่การเอาชื่อด้านบนมาต่อกัน

2. การรวมข้อความจะทำเฉพาะเมื่อมีการผสานเซลล์ใน "แนวตั้ง" เท่านั้น (คอลัมน์เดียวกันแต่มีหลายบรรทัด) 
   ให้เชื่อมข้อความด้วยเครื่องหมาย \n
   เช่น: หากชื่อหัวข้อหนึ่งครอบคลุม 2 แถวในคอลัมน์เดียว ให้รวมเป็น "A\nB"

3. หัวตารางสุดท้าย (Heads) ต้องมีจำนวนคอลัมน์ตรงกับแถวข้อมูลจริง (Data rows)

กรุณาส่งคืนผลลัพธ์ในรูปแบบ JSON ที่เข้มงวดดังนี้:
{{
  "heads": ["หัวตาราง1", "หัวตาราง2", "หัวตาราง3", ...],
  "start_row": <int>,
  "end_row": <int>
}}

รายละเอียดฟิลด์:
- heads: รายชื่อหัวตารางทั้งหมดจากซ้ายไปขวา หากมีการผสานเซลล์แนวตั้งให้เชื่อมด้วย \n
- start_row, end_row: เลขแถวเริ่มต้นและสิ้นสุดของ "พื้นที่หัวตาราง" ทั้งหมดใน Excel (เริ่มนับจาก 1)
"""

GET_EXCEL_HEAD_AND_DATA_PROMPT_EN = """
You are an expert in data analysis and table structure recognition. 
Input: Excel preview content {preview_text}. It may contain multi-line headers, merged cells, and empty cells.

Task:
Identify the final column headers (Heads) and output them as an array.

### Rules:
1. If a top-level header spans multiple columns but those columns have specific "Sub-titles" in the row below, 
   use the Sub-titles as the final headers. DO NOT concatenate the top-level title with sub-titles.
2. Only concatenate text vertically (using \n) if a header spans multiple rows within the SAME column.
3. The final 'heads' array must match the actual number of data columns.

Return strictly in JSON:
{{
  "heads": ["Header1", "Header2", ...],
  "start_row": <int>,
  "end_row": <int>
}}
Note: start_row and end_row are 1-based indices covering the entire header area.
"""
