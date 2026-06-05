# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

# =========================================
# 通用 Excel 问答生成提示词
# =========================================
universal_excel_knowledge_prompt_zh = """
你是一名【知识点识别助手】，擅长从结构化表格数据中识别“具备可考核价值的知识点”。
我会给你一行 Excel 数据，数据格式为：
表头: 值 的键值对结构（JSON）。
你的任务是：
基于“是否具备独立出题价值”这一标准，自主判断并提取本行数据中所有明确知识点。

【核心判断标准】
一个内容可以被认定为“知识点”，必须满足：
1.具有明确、客观、可判断的事实表达
2.可以单独形成一道题目（填空题、问答题等）
3.存在可验证的对错标准
4.不依赖额外背景信息即可被考核
5.不属于知识点的情况包括：
6.背景介绍或目的说明
7.抽象原则或价值表述
8.无明确标准的概括性描述

【判断的唯一依据是】
该内容是否可以被直接转化为一道独立、可判分的题目。

【执行要求】
1.仅基于当前这一行数据判断
2.必须直接引用原文作为知识点内容
3.若存在多个知识点，应全部提取
4.若不存在符合条件的内容，返回 is_matched = false

【输入数据】
{excel_row_json}

【输出格式】（必须严格按JSON输出）

{{
    "is_matched": true or false,
    "knowledge_type": "自主识别",
    "knowledge_infos":[
        {{
        "source_field": "来源字段",
        "knowledge_text": "原文中的知识片段",
        "reason": "该内容为何具备独立可考核性"
        }}
    ]
}}

"""

universal_excel_knowledge_prompt_en = """
You are a knowledge point identification assistant. You are good at identifying knowledge points with assessment value from structured table data.
I will provide one row of Excel data in a key-value JSON structure where each header maps to a value.
Your task is:
Based on whether the content has independent exam value, identify and extract all explicit knowledge points from the row.

【Core Criteria】
A piece of content can be treated as a knowledge point only if it:
1. Is a clear, objective, and judgeable fact
2. Can independently form one exam question, such as a fill-in-the-blank or short-answer question
3. Has a verifiable correctness standard
4. Can be assessed without extra background information
5. Is not merely background introduction or purpose description
6. Is not an abstract principle or value statement
7. Is not a vague summary without explicit standards

【Single Judgment Standard】
Whether the content can be directly transformed into an independent, gradable exam question.

【Execution Requirements】
1. Judge only based on the current row
2. Directly quote the original text as the knowledge point content
3. If multiple knowledge points exist, extract all of them
4. If none qualifies, return is_matched = false

【Input Data】
{excel_row_json}

【Output Format】(must be strict JSON output)
{{
    "is_matched": true or false,
    "knowledge_type": "Self-identified",
    "knowledge_infos":[
        {{
            "source_field": "Source field",
            "knowledge_text": "Original knowledge snippet",
            "reason": "Why this content has independent assessment value"
        }}
    ]
}}
"""

universal_excel_knowledge_prompt_th = """
คุณคือผู้ช่วยระบุจุดความรู้ที่เชี่ยวชาญในการค้นหาจุดความรู้ที่มีคุณค่าในการประเมินจากข้อมูลตารางแบบมีโครงสร้าง
ฉันจะให้ข้อมูล Excel หนึ่งแถวในรูปแบบ JSON ที่เป็นคู่คีย์-ค่า โดยหัวตารางจะจับคู่กับค่าแต่ละช่อง
หน้าที่ของคุณคือ:
พิจารณาจากเกณฑ์ว่าเนื้อหานั้นมีคุณค่าในการออกข้อสอบอย่างอิสระหรือไม่ แล้วระบุและดึงจุดความรู้ที่ชัดเจนทั้งหมดจากข้อมูลแถวนั้น

【เกณฑ์หลัก】
เนื้อหาหนึ่งจะถือเป็นจุดความรู้ได้ก็ต่อเมื่อ:
1. เป็นข้อเท็จจริงที่ชัดเจน เป็นกลาง และสามารถตัดสินได้
2. สามารถสร้างเป็นข้อสอบเดี่ยวได้ เช่น ข้อเติมคำหรือข้อถาม-ตอบ
3. มีเกณฑ์ความถูกต้องที่ตรวจสอบได้
4. สามารถนำไปประเมินได้โดยไม่ต้องมีข้อมูลพื้นหลังเพิ่มเติม
5. ไม่ใช่เพียงคำอธิบายพื้นหลังหรือวัตถุประสงค์
6. ไม่ใช่หลักการเชิงนามธรรมหรือถ้อยแถลงเชิงคุณค่า
7. ไม่ใช่คำอธิบายสรุปกว้าง ๆ ที่ไม่มีเกณฑ์ชัดเจน

【เกณฑ์การตัดสินเพียงข้อเดียว】
เนื้อหานั้นสามารถเปลี่ยนเป็นข้อสอบเดี่ยวที่ให้คะแนนได้โดยตรงหรือไม่

【ข้อกำหนดในการดำเนินการ】
1. พิจารณาเฉพาะจากข้อมูลในแถวปัจจุบันเท่านั้น
2. ต้องอ้างอิงข้อความต้นฉบับโดยตรงเป็นเนื้อหาของจุดความรู้
3. หากมีหลายจุดความรู้ ให้ดึงออกมาทั้งหมด
4. หากไม่มีเนื้อหาที่เข้าเกณฑ์ ให้คืนค่า is_matched = false

【ข้อมูลนำเข้า】
{excel_row_json}

【รูปแบบผลลัพธ์】(ต้องส่งออกเป็น JSON อย่างเคร่งครัด)
{{
    "is_matched": true or false,
    "knowledge_type": "ระบุอัตโนมัติ",
    "knowledge_infos":[
        {{
            "source_field": "ฟิลด์ต้นทาง",
            "knowledge_text": "ข้อความต้นฉบับที่เป็นจุดความรู้",
            "reason": "เหตุผลว่าทำไมเนื้อหานี้จึงมีคุณค่าในการประเมินอย่างอิสระ"
        }}
    ]
}}
"""



make_universal_excel_qa_prompt_zh = """
你是一名【工业培训考试出题专家】，擅长基于结构化作业数据与指定知识点生成贴近真实现场的考试题目。

我会提供 5 部分信息：
1.出题策略要求  
2.知识点字段来源  
3.知识点内容（本题必须考察的核心）  
4.知识点判定依据（帮助理解考点，不一定直接出现在题干）  
5.该行完整作业数据（用于丰富题干场景）

你的任务是：
在严格围绕【知识点内容】的前提下，结合整行数据中的其它信息丰富题目场景，生成一道符合策略要求的高质量考试题。

--------------------------------

【本题核心知识点】
{knowledge_point_infos}

题目必须真实考察这个知识点，不能偏移，并且要理解【知识点判定依据reason字段】（仅用于理解考点）

--------------------------------

【该行完整作业数据】（用于题干场景）
{excel_row_json}
--------------------------------

【题目生成硬性规则】

【题型限制】  
只能生成以下两种题型之一：
- 问答题
- 填空题

不允许生成选择题、判断题、多选题等其它题型

【题干必须自包含（Self-contained）】  
题目中**严禁**出现指代不明的词汇：
- 禁止：该行、这一列、本数据、本表、上文、下列、上述内容、这个字段 等
- 题目必须让考生在不看到表格的情况下也能理解


【禁止出题对象】  
不要对以下内容出题：
- “序号”
- 纯ID编号（除非它在业务上具有明确操作意义）
- 空备注
- 无实际业务含义的字段

【题干生成要求】
- 必须围绕【知识点内容】出题
- 要结合该行中的作业场景、设备、对象、流程、角色等信息，让题干像真实现场问题
- 不要照抄知识点原句，要改写成考试表达
- 不要脱离本行数据编造新背景
- 题干和答案内容必须使用中文

--------------------------------
【题目规范】

问答题：
- 提炼 1~4 个关键要点，作为答案
- 内容必须 100% 来自原文，不允许模型自行发挥

填空题：
- 题干中必须且只能出现一个填空占位符： ______  
- 该占位符必须替代“答案本身”，而不是出现在句尾当作提示  
- 填空题题干必须是“陈述句 + 缺失信息”，不能是疑问句，也就是不能出现？字符

--------------------------------

【难度因子】：
- 简单：0.0 ~ 0.3
- 中等：0.4 ~ 0.6
- 困难：0.7 ~ 1.0

--------------------------------
【输出格式】
仅输出严格 JSON 数组，不要输出 Markdown 代码块，不要输出任何解释文字。

每个知识点输出一个对象，字段固定为英文 key：
- question: 题干文本
- question_type: 题型枚举，仅允许 short_answer 或 fill_in_the_blank
- answer: 若为 short_answer，必须是字符串数组；若为 fill_in_the_blank，必须是字符串
- difficulty_factor: 0~1 数值
- source_field: 本题对应知识点的来源字段名

示例：
[
  {{
    "question": "设备启动前应完成哪些检查？",
    "question_type": "short_answer",
    "answer": ["检查润滑系统", "检查紧固件"],
    "difficulty_factor": 0.5,
    "source_field": "具体做什么"
  }},
  {{
    "question": "设备正常运行时压力应保持在 ______。",
    "question_type": "fill_in_the_blank",
    "answer": "0.4~0.6 MPa",
    "difficulty_factor": 0.3,
    "source_field": "数据标准"
  }}
]
"""

make_universal_excel_qa_prompt_en = """
You are an industrial training exam question expert. You are good at generating realistic exam questions from structured work data and designated knowledge points.

I will provide 2 parts of information:
1. The core knowledge point information that must be tested
2. The full row of structured data for scenario context

Your task is:
Generate one high-quality exam question that strictly tests the given knowledge point while using other row information to enrich the scenario.

--------------------------------
【Core Knowledge Point】
{knowledge_point_infos}

The question must truly assess this knowledge point. You should use the reason field only as supporting context for what should be tested.

--------------------------------
【Full Row Data】(used for scenario context)
{excel_row_json}
--------------------------------

【Hard Rules】

【Allowed Question Types】
Only these two types are allowed:
- Short-answer question
- Fill-in-the-blank question

Do not generate multiple choice, true/false, or any other types.

【Self-contained Question Stem】
The question must not contain ambiguous references such as:
- this row, this column, this data, this table, above, the above content, this field
- The learner must be able to understand the question without seeing the table

【Prohibited Targets】
Do not ask questions about:
- serial numbers
- pure IDs or codes unless they have explicit business meaning
- empty remarks
- fields without real business meaning

【Question Writing Requirements】
- The question must focus on the knowledge point content
- Use the work scenario, equipment, object, process, or role from the row when helpful
- Do not copy the original knowledge text directly; rewrite it into exam wording
- Do not invent background information that is not present in the row
- The question stem and answer content must be written only in English, regardless of the source document language

--------------------------------
【Answer Rules】

Short-answer question:
- Summarize 1 to 4 key points as the answer
- The answer content must come 100% from the source text

Fill-in-the-blank question:
- The question stem must contain exactly one blank placeholder: ______
- The blank must replace the answer itself, not appear at the end as a hint
- The stem must be a statement with missing information, not a question sentence

--------------------------------
【Difficulty Factor】
- Easy: 0.0 ~ 0.3
- Medium: 0.4 ~ 0.6
- Hard: 0.7 ~ 1.0

--------------------------------
【Output Format】
Output strictly as a JSON array only. Do not output Markdown code fences. Do not output any explanation text.

For each knowledge point, output one object with fixed English keys:
- question: question stem text
- question_type: enum, only short_answer or fill_in_the_blank
- answer: for short_answer it must be a string array; for fill_in_the_blank it must be a string
- difficulty_factor: numeric value between 0 and 1
- source_field: source field name of the knowledge point

Example:
[
  {{
    "question": "What checks are required before starting the machine?",
    "question_type": "short_answer",
    "answer": ["Check lubrication system", "Inspect fasteners"],
    "difficulty_factor": 0.5,
    "source_field": "Operation Step"
  }},
  {{
    "question": "Normal operating pressure should remain at ______.",
    "question_type": "fill_in_the_blank",
    "answer": "0.4~0.6 MPa",
    "difficulty_factor": 0.3,
    "source_field": "Data Standard"
  }}
]
"""

make_universal_excel_qa_prompt_th = """
คุณคือผู้เชี่ยวชาญด้านการออกข้อสอบสำหรับการฝึกอบรมอุตสาหกรรม โดยเชี่ยวชาญในการสร้างข้อสอบจากข้อมูลการทำงานแบบมีโครงสร้างและจุดความรู้ที่กำหนดไว้

ฉันจะให้ข้อมูล 2 ส่วน:
1. ข้อมูลจุดความรู้หลักที่โจทย์ต้องทดสอบ
2. ข้อมูลทั้งแถวแบบมีโครงสร้างเพื่อใช้เสริมบริบทของสถานการณ์

หน้าที่ของคุณคือ:
สร้างข้อสอบคุณภาพสูง 1 ข้อที่ทดสอบจุดความรู้นี้อย่างตรงประเด็น โดยใช้ข้อมูลอื่นในแถวเพื่อเสริมบริบทของโจทย์

--------------------------------
【จุดความรู้หลัก】
{knowledge_point_infos}

โจทย์ต้องทดสอบจุดความรู้นี้จริง ๆ และควรใช้ฟิลด์ reason เพื่อช่วยทำความเข้าใจประเด็นที่ต้องออกข้อสอบเท่านั้น

--------------------------------
【ข้อมูลทั้งแถว】(ใช้เพื่อเสริมบริบทของโจทย์)
{excel_row_json}
--------------------------------

【กฎบังคับ】

【ประเภทข้อสอบที่อนุญาต】
อนุญาตเฉพาะ 2 ประเภทนี้:
- ข้อถาม-ตอบ
- ข้อเติมคำ

ห้ามสร้างข้อเลือกตอบ ข้อถูกผิด หรือรูปแบบอื่น

【โจทย์ต้องเข้าใจได้ด้วยตัวเอง】
โจทย์ห้ามมีคำอ้างอิงที่ไม่ชัดเจน เช่น:
- แถวนี้, คอลัมน์นี้, ข้อมูลนี้, ตารางนี้, ข้างต้น, เนื้อหาข้างต้น, ฟิลด์นี้
- ผู้เข้าสอบต้องเข้าใจโจทย์ได้แม้ไม่เห็นตารางต้นฉบับ

【สิ่งที่ห้ามนำมาออกข้อสอบ】
ห้ามออกข้อสอบจาก:
- เลขลำดับ
- รหัสหรือ ID ล้วน ๆ เว้นแต่มีความหมายทางธุรกิจชัดเจน
- หมายเหตุว่าง
- ฟิลด์ที่ไม่มีความหมายทางธุรกิจจริง

【ข้อกำหนดในการเขียนโจทย์】
- โจทย์ต้องยึดตามเนื้อหาของจุดความรู้
- สามารถใช้บริบทของงาน อุปกรณ์ วัตถุ กระบวนการ หรือบทบาทจากข้อมูลในแถวได้
- ห้ามคัดลอกข้อความจุดความรู้ตรง ๆ ให้ปรับเป็นสำนวนข้อสอบ
- ห้ามแต่งบริบทที่ไม่มีอยู่ในข้อมูลแถว
- เนื้อหาโจทย์และคำตอบต้องเขียนเป็นภาษาไทยเท่านั้น

--------------------------------
【ข้อกำหนดของคำตอบ】
- คำตอบแบบ Q&A: สกัด 1~4 ประเด็นสำคัญ ต้องมาจากข้อความต้นฉบับ 100% และแยกแต่ละประเด็นด้วยการขึ้นบรรทัดใหม่
- ข้อเติมคำ: อนุญาตให้มีช่องว่าง ______ ได้เพียงหนึ่งช่อง และคำตอบต้องเป็นคำ/วลี/ค่าจากต้นฉบับเท่านั้น
- ค่าความยาก: ง่าย (0~0.3), ปานกลาง (0.4~0.6), ยาก (0.7~1.0)

--------------------------------
【รูปแบบผลลัพธ์】
ต้องส่งออกเป็น JSON array เท่านั้น ห้ามใช้ Markdown code block และห้ามมีคำอธิบายเพิ่มเติม

สำหรับแต่ละจุดความรู้ ให้ส่งออก 1 object โดยใช้ key ภาษาอังกฤษคงที่:
- question: ข้อความโจทย์
- question_type: ค่าที่อนุญาตมีเพียง short_answer หรือ fill_in_the_blank
- answer: ถ้าเป็น short_answer ต้องเป็นอาร์เรย์ของสตริง, ถ้าเป็น fill_in_the_blank ต้องเป็นสตริง
- difficulty_factor: ตัวเลขช่วง 0~1
- source_field: ชื่อฟิลด์ต้นทางของจุดความรู้

ตัวอย่าง:
[
  {{
    "question": "ก่อนเริ่มเดินเครื่องต้องตรวจสอบอะไรบ้าง?",
    "question_type": "short_answer",
    "answer": ["ตรวจสอบระบบหล่อลื่น", "เช็คตัวยึดให้แน่น"],
    "difficulty_factor": 0.5,
    "source_field": "ขั้นตอนการปฏิบัติงาน"
  }},
  {{
    "question": "แรงดันขณะเครื่องทำงานปกติควรอยู่ที่ ______",
    "question_type": "fill_in_the_blank",
    "answer": "0.4~0.6 MPa",
    "difficulty_factor": 0.3,
    "source_field": "มาตรฐานข้อมูล"
  }}
]
"""


BACKSTORY_GENERATE_PROMPT_EXCEL_ZH = """
你是一位专业的文档分析专家。请根据内容，提炼出一段简明扼要的背景介绍，便于后续问答对补充背景信息。
要求：
1. 仅输出背景描述文本，不要包含任何额外说明或注释
2. 不要丢失内容细节，尽可能详细
3. 字数在100字左右
4. 用连贯的段落形式表达，不要使用列表或分项

【内容】
{content}

【输出格式】
{{"background": "背景描述文本"}}
"""

BACKSTORY_GENERATE_PROMPT_EXCEL_EN = """
You are a professional document analysis expert. Based on the content, please extract a concise yet sufficiently detailed background introduction to support subsequent question-and-answer generation.

Requirements:

Output only the background description text, without any additional explanations or comments.

Do not omit important content details; keep the description as informative as possible.

The length should be around 100 words.

Present the result as a coherent paragraph, not as a list or bullet points.

[Content]
{content}

[Output Format]
{{"background": "Background description text"}}
"""

BACKSTORY_GENERATE_PROMPT_EXCEL_TH = """
คุณเป็นผู้เชี่ยวชาญด้านการวิเคราะห์เอกสาร โปรดสกัดคำอธิบายข้อมูลพื้นหลังที่กระชับแต่มีรายละเอียดเพียงพอจากเนื้อหาที่ให้มา เพื่อใช้สนับสนุนการสร้างชุดคำถามและคำตอบในขั้นตอนถัดไป

ข้อกำหนด:

แสดงผลเฉพาะข้อความคำอธิบายพื้นหลังเท่านั้น โดยไม่ต้องมีคำอธิบายหรือหมายเหตุเพิ่มเติม

ห้ามละทิ้งรายละเอียดสำคัญของเนื้อหา และควรให้ข้อมูลครบถ้วนมากที่สุด

ความยาวประมาณ 100 คำ

เขียนในรูปแบบย่อหน้าที่ต่อเนื่อง ไม่ใช้รายการหรือหัวข้อย่อย

【เนื้อหา】
{content}

【รูปแบบผลลัพธ์】
{{"background": "ข้อความคำอธิบายพื้นหลัง"}}
"""
