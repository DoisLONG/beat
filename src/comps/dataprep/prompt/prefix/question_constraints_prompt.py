# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0


total_knowledge_constraint_prompt_template = """
你是一名【工业知识点识别助手】，擅长从结构化表格数据中识别“可用于出题的知识点”。

我会给你一行 Excel 数据，数据格式为表头: 值的键值对结构。

你的任务是：
根据指定的【知识点识别规则】，判断这行数据中是否包含符合规则的“明确知识点”。

⚠注意：
1. 只依据这一行数据本身判断，不要联想外部知识
2. 必须是“可以被直接用于出题”的明确知识，而不是背景描述或目的说明
3. 如果只是流程背景、管理描述、无具体操作/判断标准/数据要求，则不算知识点

-----------------------------
【当前知识点识别规则】
{strategy}
-----------------------------

【输入数据】
{excel_row_json}

-----------------------------
【输出要求】（必须严格按JSON输出）

{{
  "is_matched": true or false,
  "knowledge_type": "（若命中，填写对应规则名称，否则填 无）",
  "knowledge_infos":[
    {{
        "source_field": "来自哪一个表头字段",
        "knowledge_text": "直接从原文中摘取的关键知识片段",
        "reason": "为什么这句话符合 / 不符合 该规则（简要说明判断逻辑）"
    }}
  ]
}}

"""

total_knowledge_constraint_prompt_template_en = """
You are an 【Industrial Knowledge Point Identification Assistant】, specialized in identifying “knowledge points that can be used to generate exam questions” from structured tabular data.

I will provide you with one row of Excel data in the format of key-value pairs (column header: value).

Your task is:
Based on the specified 【Knowledge Point Identification Rules】, determine whether this row contains any “explicit knowledge points” that meet the rules.

⚠ Important Notes:
1. Only judge based on the content of this single row. Do NOT use external knowledge.
2. The knowledge must be something that “can be directly used to create a question,” not background description or purpose statements.
3. If the content is only process background, management description, or lacks specific operational steps / decision criteria / numerical or standard-based requirements, it does NOT count as a knowledge point.

-----------------------------
【Current Knowledge Point Identification Rules】
{strategy}
-----------------------------

【Input Data】
{excel_row_json}

-----------------------------
【Output Requirements】 (Must be strictly in JSON format)

{{
  "is_matched": true or false,
  "knowledge_type": "(If matched, fill in the corresponding rule name; otherwise fill in 无)",
  "knowledge_infos":[
    {{
      "source_field": "Which column header this comes from",
      "knowledge_text": "The key knowledge snippet directly quoted from the original text",
      "reason": "Brief explanation of why this sentence does or does not meet the rule"
    }}
  ]
}}
"""

total_knowledge_constraint_prompt_template_th = """
คุณคือผู้ช่วย【ระบุจุดความรู้ด้านอุตสาหกรรม】ที่เชี่ยวชาญในการระบุ “จุดความรู้ที่สามารถนำไปออกข้อสอบได้” จากข้อมูลตารางแบบมีโครงสร้าง

ฉันจะให้ข้อมูลจาก Excel มา 1 แถว โดยอยู่ในรูปแบบ คู่ค่า:ค่า (ชื่อคอลัมน์: ค่า)

หน้าที่ของคุณคือ:
ตาม【กฎการระบุจุดความรู้】ที่กำหนด ให้พิจารณาว่าข้อมูลแถวนี้มี “จุดความรู้ที่ชัดเจน” ที่ตรงตามกฎหรือไม่

⚠ ข้อควรระวัง:
1. พิจารณาเฉพาะข้อมูลในแถวนี้เท่านั้น ห้ามอ้างอิงความรู้ภายนอก
2. ต้องเป็นความรู้ที่ “สามารถนำไปออกข้อสอบได้โดยตรง” ไม่ใช่คำอธิบายพื้นหลังหรือวัตถุประสงค์
3. หากเป็นเพียงคำอธิบายกระบวนการ ภาพรวมการจัดการ หรือไม่มีมาตรฐานการปฏิบัติ/เกณฑ์การตัดสิน/ข้อกำหนดเชิงตัวเลขที่ชัดเจน จะไม่ถือว่าเป็นจุดความรู้

-----------------------------
【กฎการระบุจุดความรู้ปัจจุบัน】
{strategy}
-----------------------------

【ข้อมูลนำเข้า】
{excel_row_json}

-----------------------------
【รูปแบบผลลัพธ์】 (ต้องส่งออกเป็น JSON เท่านั้น)

{{
  "is_matched": true หรือ false,
  "knowledge_type": "（หากตรงตามกฎ ให้ระบุชื่อกฎ มิฉะนั้นให้ใส่ 无）",
  "knowledge_infos":[
    {{
      "source_field": "มาจากคอลัมน์ใด",
      "knowledge_text": "ข้อความความรู้สำคัญที่คัดลอกตรงจากต้นฉบับ",
      "reason": "เหตุผลสั้น ๆ ว่าทำไมข้อความนี้จึงตรง / ไม่ตรง กับกฎนี้"
    }}
  ]
}}
"""

step_strategy_prompt = """
识别“具体操作步骤类知识点”，需要满足：

✔ 必须是“人需要执行的动作或操作”
✔ 通常包含动词，例如：检查、确认、记录、测量、调整、安装、拆除、启动、关闭等
✔ 描述的是“做什么”，而不是“为什么做”

以下情况不算：
- 作业目的、背景说明
- 管理要求（如“需符合规范”）
- 结果描述（如“确保安全”）
- 纯名词性短语（如“设备点检作业”）

只有当内容可以直接变成“操作类考题”时，才算命中
知识点类型填写：操作步骤
"""

step_strategy_prompt_en = """
Identification of “Operational Step Knowledge Points” must meet the following:

✔ It must be an action or operation that a person needs to perform
✔ It usually contains verbs, such as: check, confirm, record, measure, adjust, install, remove, start, shut down, etc.
✔ It describes “what to do”, not “why it is done”

The following do NOT count:

Work objectives or background explanations

Management or compliance requirements (e.g., “must comply with regulations”)

Result descriptions (e.g., “ensure safety”)

Pure noun phrases (e.g., “equipment inspection operation”)

Only when the content can be directly turned into an operation-based exam question should it be considered a match.

Knowledge type to fill in: Operational Step
"""

step_strategy_prompt_th = """
การระบุ “จุดความรู้ประเภทขั้นตอนการปฏิบัติงาน” ต้องเป็นไปตามเงื่อนไขต่อไปนี้:

✔ ต้องเป็นการกระทำหรือขั้นตอนที่มนุษย์ต้องลงมือปฏิบัติ
✔ มักมีคำกริยา เช่น ตรวจสอบ ยืนยัน บันทึก วัด ปรับ ติดตั้ง ถอดออก เริ่มต้น ปิดเครื่อง เป็นต้น
✔ อธิบายว่า “ต้องทำอะไร” ไม่ใช่ “ทำไปเพื่ออะไร”

กรณีต่อไปนี้ ไม่ถือว่าเป็นจุดความรู้ประเภทนี้:

วัตถุประสงค์ของงาน หรือคำอธิบายพื้นหลัง

ข้อกำหนดด้านการบริหารหรือการปฏิบัติตามกฎ (เช่น “ต้องเป็นไปตามข้อกำหนด”)

คำอธิบายผลลัพธ์ (เช่น “เพื่อความปลอดภัย”)

วลีที่เป็นคำนามล้วน ๆ (เช่น “งานตรวจสอบอุปกรณ์”)

จะถือว่าตรงเงื่อนไข ก็ต่อเมื่อเนื้อหานั้นสามารถนำไปสร้างเป็น ข้อสอบประเภทการปฏิบัติงาน ได้โดยตรงเท่านั้น

ประเภทจุดความรู้ที่ต้องกรอก: ขั้นตอนการปฏิบัติงาน
"""



error_strategy_prompt = """
识别“异常情况或异常排查处理类知识点”，需要满足：

✔ 描述的是“当出现某种异常情况时应如何判断、排查或处理”
✔ 通常包含关键词：异常、故障、未达标、不正常、偏差、超标、报警、失效等
✔ 或包含处理动作：排查、检查原因、重新调整、更换、停止使用等

必须体现出：
异常现象” + “对应处理/判断方式”（可以只出现其中之一，但要明显是异常场景）

以下情况不算：
- 正常操作流程
- 纯预防性检查（未涉及异常）
- 纯结果描述（如“否则会影响质量”）

知识点类型填写：异常处理
"""

error_strategy_prompt_en = """
Identification of “Abnormal Situation or Troubleshooting Knowledge Points” must meet the following:

✔ It describes how to judge, investigate, or handle a situation when an abnormal condition occurs
✔ It usually includes keywords such as: abnormal, fault, failure, not up to standard, irregular, deviation, out of limit, alarm, malfunction, etc.
✔ Or includes handling actions such as: troubleshoot, check the cause, readjust, replace, stop using, etc.

It must reflect:
An abnormal phenomenon + a corresponding handling or judgment method
(One of them may appear alone, but it must clearly indicate an abnormal scenario.)

The following do NOT count:

Normal operating procedures

Purely preventive inspections (without any abnormal condition)

Pure result descriptions (e.g., “otherwise it will affect quality”)

Knowledge type to fill in: Abnormal Handling
"""

error_strategy_prompt_th = """
การระบุ “จุดความรู้ประเภทสถานการณ์ผิดปกติหรือการวิเคราะห์แก้ไขปัญหา” ต้องเป็นไปตามเงื่อนไขต่อไปนี้:

✔ อธิบายว่า เมื่อเกิดสถานการณ์ผิดปกติ ควรพิจารณา ตรวจสอบ หรือดำเนินการแก้ไขอย่างไร
✔ มักมีคำสำคัญ เช่น ผิดปกติ ขัดข้อง ล้มเหลว ไม่ได้มาตรฐาน ไม่ปกติ ค่าคลาดเคลื่อน เกินค่ากำหนด สัญญาณเตือน อุปกรณ์เสีย เป็นต้น
✔ หรือมีการกระทำเพื่อจัดการปัญหา เช่น ตรวจหาสาเหตุ ปรับใหม่ เปลี่ยนชิ้นส่วน หยุดใช้งาน เป็นต้น

ต้องสะท้อนให้เห็น:
อาการหรือสถานการณ์ผิดปกติ + วิธีการตัดสินใจหรือการจัดการที่สอดคล้องกัน
(อาจปรากฏเพียงอย่างใดอย่างหนึ่งได้ แต่ต้องชัดเจนว่าเป็นบริบทของความผิดปกติ)

กรณีต่อไปนี้ ไม่ถือว่าเป็นจุดความรู้ประเภทนี้:

ขั้นตอนการปฏิบัติงานตามปกติ

การตรวจสอบเชิงป้องกันล้วน ๆ (ที่ไม่ได้กล่าวถึงความผิดปกติ)

คำอธิบายผลลัพธ์เพียงอย่างเดียว (เช่น “มิฉะนั้นจะกระทบต่อคุณภาพ”)

ประเภทจุดความรู้ที่ต้องกรอก: การจัดการกรณีผิดปกติ
"""


data_strategy_prompt ="""
识别“数据标准、指标要求、数值范围类知识点”，需要满足：

✔ 包含明确的数据、数值、范围或可量化标准
✔ 如：时间、温度、压力、尺寸、数量、频率、比例、阈值、合格标准等
✔ 或出现表达标准的词：≥、≤、范围、不得超过、保持在、控制在、误差±等

本质是：这句话提供了“可量化判断依据”

以下情况不算：
- 模糊表述（如“适当”“少量”“必要时”）
- 没有具体数值的原则性要求
- 纯操作动作但无数据标准

知识点类型填写：数据标准
"""

data_strategy_prompt_en = """
Identification of “Data Standards, Indicator Requirements, or Numerical Range Knowledge Points” must meet the following:

✔ It contains clear data, numerical values, ranges, or quantifiable standards
✔ Examples include: time, temperature, pressure, dimensions, quantity, frequency, ratio, thresholds, acceptance criteria, etc.
✔ Or includes expressions that indicate standards, such as: ≥, ≤, range, must not exceed, maintain at, control within, tolerance ±, etc.

Essentially:
The sentence provides a quantifiable basis for judgment.

The following do NOT count:

Vague expressions (e.g., “appropriate”, “a small amount”, “when necessary”)

Principle-based requirements without specific numbers

Pure operational actions without any data or numerical standards

Knowledge type to fill in: Data Standard
"""

data_strategy_prompt_th = """
การระบุ “จุดความรู้ประเภทมาตรฐานข้อมูล ตัวชี้วัด หรือช่วงค่าตัวเลข” ต้องเป็นไปตามเงื่อนไขต่อไปนี้:

✔ มี ข้อมูล ตัวเลข ช่วงค่า หรือมาตรฐานที่สามารถวัดเชิงปริมาณได้อย่างชัดเจน
✔ ตัวอย่างเช่น เวลา อุณหภูมิ ความดัน ขนาด ปริมาณ ความถี่ สัดส่วน ค่าเกณฑ์ หรือเกณฑ์การผ่าน เป็นต้น
✔ หรือมีคำที่ใช้แสดงมาตรฐาน เช่น ≥, ≤, ช่วงค่า, ห้ามเกิน, รักษาให้อยู่ที่, ควบคุมให้อยู่ใน, ค่าความคลาดเคลื่อน ± เป็นต้น

สาระสำคัญคือ:
ประโยคดังกล่าวให้ เกณฑ์การตัดสินเชิงปริมาณที่ชัดเจน

กรณีต่อไปนี้ ไม่ถือว่าเป็นจุดความรู้ประเภทนี้:

คำอธิบายที่คลุมเครือ (เช่น “เหมาะสม”, “เล็กน้อย”, “เมื่อจำเป็น”)

ข้อกำหนดเชิงหลักการที่ไม่มีตัวเลขชัดเจน

คำอธิบายการปฏิบัติงานล้วน ๆ ที่ไม่มีมาตรฐานตัวเลข

ประเภทจุดความรู้ที่ต้องกรอก: มาตรฐานข้อมูล
"""


generate_constraint_qa_prompt = """
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
【出题策略要求】
{question_strategy}
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
【答案规范】

问答题：
- 提炼 1~4 个关键要点，作为答案
- 内容必须 100% 来自原文，不允许模型自行发挥

填空题：
- 题干中必须且只能出现一个填空占位符： ______  
- 该占位符必须替代“答案本身”，而不是出现在句尾当作提示  
- 填空题题干必须是“陈述句 + 缺失信息”，不能是疑问句  

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

generate_constraint_qa_prompt_en = """
You are an 【Industrial Training Exam Question Expert】, skilled at generating realistic, field-oriented exam questions based on structured operational data and specified knowledge points.

I will provide 5 parts of information:

Question strategy requirements

Source fields of the knowledge points

Knowledge point content (the core that this question must assess)

Knowledge point judgment basis (helps understand the test focus, may not appear directly in the question)

The full operational data of this row (used to enrich the scenario in the question)

Your task is:
Strictly focusing on the 【Knowledge Point Content】, use other information in the same row to enrich the scenario, and generate one high-quality exam question that meets the strategy requirements.

【Question Strategy Requirements】
{question_strategy}

【Core Knowledge Point for This Question】
{knowledge_point_infos}

The question must truly assess this knowledge point and must not deviate. You should understand the “reason” field in the knowledge point judgment basis (for understanding only, not necessarily shown in the question).

【Full Operational Data of This Row】 (for building the scenario)
{excel_row_json}

【Hard Rules for Question Generation】

【Allowed Question Types】
Only one of the following two types may be generated:

Short-answer question

Fill-in-the-blank question

Do NOT generate multiple choice, true/false, or any other types.

【The Question Must Be Self-contained】
The question must NOT contain unclear references such as:

“this row”, “this column”, “this data”, “this table”, “above”, “below”, “the following”, “this field”, etc.
The question must be understandable without seeing the original table.

【Prohibited Question Targets】
Do NOT create questions about:

“Serial number”

Pure ID numbers (unless they have clear operational meaning)

Empty remarks

Fields without real business meaning

【Question Stem Requirements】

The question must revolve around the 【Knowledge Point Content】

Incorporate the operational context such as scenario, equipment, object, process, and role from this row, making it sound like a real on-site situation

Do not copy the original knowledge sentence directly; rewrite it in an exam style

Do not fabricate new background unrelated to this row

The question stem and answer content must be written only in English, regardless of the source document language

【Answer Rules】

For short-answer questions:

Extract 1–4 key points as the answer

The content must come 100% from the original text, with no additional invention

For fill-in-the-blank questions:

The question must contain exactly one blank placeholder: ______

The blank must replace the answer itself, not appear at the end as a hint

The stem must be a statement with missing information, NOT a question sentence

【Difficulty Factor】:

Easy: 0.0 ~ 0.3

Medium: 0.4 ~ 0.6

Hard: 0.7 ~ 1.0

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

generate_constraint_qa_prompt_th = """
คุณคือผู้เชี่ยวชาญด้าน【การออกข้อสอบฝึกอบรมอุตสาหกรรม】ที่มีความสามารถในการสร้างข้อสอบเสมือนจริงจากข้อมูลการปฏิบัติงานแบบมีโครงสร้างและจุดความรู้ที่กำหนด

ฉันจะให้ข้อมูล 5 ส่วน:

ข้อกำหนดกลยุทธ์การออกข้อสอบ

แหล่งที่มาของฟิลด์จุดความรู้

เนื้อหาจุดความรู้ (แก่นหลักที่ข้อนี้ต้องวัด)

เหตุผลในการจัดเป็นจุดความรู้ (ใช้เพื่อทำความเข้าใจประเด็นสอบ อาจไม่ปรากฏตรงในโจทย์)

ข้อมูลการปฏิบัติงานทั้งหมดของแถวนี้ (ใช้เสริมบริบทของโจทย์)

หน้าที่ของคุณคือ:
ภายใต้เงื่อนไขที่ต้องยึดตาม【เนื้อหาจุดความรู้】อย่างเคร่งครัด ให้ใช้ข้อมูลอื่น ๆ ในแถวเดียวกันมาสร้างบริบท และสร้างข้อสอบคุณภาพสูงจำนวน 1 ข้อที่ตรงตามกลยุทธ์ที่กำหนด

【ข้อกำหนดกลยุทธ์การออกข้อสอบ】
{question_strategy}

【จุดความรู้หลักของข้อนี้】
{knowledge_point_infos}

โจทย์ต้องวัดจุดความรู้นี้จริง ๆ และต้องไม่เบี่ยงเบน ควรเข้าใจข้อมูลในฟิลด์ “reason” เพื่อช่วยตีความจุดประสงค์ของข้อสอบ (ใช้เพื่อความเข้าใจเท่านั้น ไม่จำเป็นต้องแสดงในโจทย์)

【ข้อมูลการปฏิบัติงานทั้งหมดของแถวนี้】 (ใช้สร้างบริบทของโจทย์)
{excel_row_json}

【กฎบังคับในการสร้างข้อสอบ】

【ประเภทข้อสอบที่อนุญาต】
สามารถสร้างได้เพียงประเภทใดประเภทหนึ่งเท่านั้น:

ข้อสอบแบบอัตนัย (ตอบสั้น)

ข้อสอบแบบเติมคำในช่องว่าง

ห้ามสร้างข้อสอบแบบปรนัย ถูก/ผิด หรือประเภทอื่นใด

【โจทย์ต้องเข้าใจได้ด้วยตัวเอง】
ห้ามใช้คำอ้างอิงที่ไม่ชัดเจน เช่น:
“แถวนี้”, “คอลัมน์นี้”, “ข้อมูลนี้”, “ตารางนี้”, “ด้านบน”, “ด้านล่าง”, “ข้อมูลข้างต้น”, “ฟิลด์นี้” เป็นต้น
ผู้สอบต้องเข้าใจโจทย์ได้โดยไม่ต้องเห็นตารางต้นฉบับ

【เนื้อหาที่ห้ามนำมาออกข้อสอบ】
ห้ามตั้งคำถามเกี่ยวกับ:

“ลำดับที่”

หมายเลข ID ล้วน ๆ (ยกเว้นมีความหมายเชิงปฏิบัติงานชัดเจน)

หมายเหตุที่ว่างเปล่า

ฟิลด์ที่ไม่มีความหมายเชิงธุรกิจจริง

【ข้อกำหนดการเขียนโจทย์】

ต้องยึดตาม【เนื้อหาจุดความรู้】เป็นหลัก

ต้องผสานบริบทการทำงาน เช่น สถานการณ์ อุปกรณ์ วัตถุ กระบวนการ หรือบทบาท จากข้อมูลแถวนี้ ให้เหมือนเหตุการณ์จริง

ห้ามคัดลอกประโยคความรู้เดิมตรง ๆ ต้องเขียนใหม่ในรูปแบบข้อสอบ

ห้ามแต่งบริบทใหม่ที่ไม่มีในข้อมูลแถวนี้

เนื้อหาโจทย์และคำตอบต้องเขียนเป็นภาษาไทยเท่านั้น

【หลักเกณฑ์คำตอบ】

ข้อสอบแบบอัตนัย:

สรุปคำตอบเป็นประเด็นสำคัญ 1–4 ข้อ

เนื้อหาคำตอบต้องมาจากต้นฉบับ 100% ห้ามแต่งเพิ่ม

ข้อสอบแบบเติมคำ:

ในโจทย์ต้องมีช่องว่างเพียงหนึ่งตำแหน่ง: ______

ช่องว่างต้องแทน “คำตอบโดยตรง” ไม่ใช่วางท้ายประโยคเป็นคำใบ้

โจทย์ต้องเป็นประโยคบอกเล่าที่ข้อมูลหายไป ไม่ใช่ประโยคคำถาม

【ระดับความยาก】

ง่าย: 0.0 ~ 0.3

ปานกลาง: 0.4 ~ 0.6

ยาก: 0.7 ~ 1.0

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


WORD_CHAPTER_KNOWLEDGE_PROMPT = """
你是一名【工业知识点识别助手】，擅长从作业文档章节中识别“可用于出题的明确知识点”。

我会提供一个完整章节的正文内容。

你的任务是：
根据指定的【知识点识别规则】，从正文中找出所有符合规则的知识点。

⚠注意：
1. 只依据本章节内容判断
2. 必须是“可以直接用于出题”的明确知识
3. 每个知识点必须是正文中的一句或一小段原文
4. 背景说明、目的描述、原则性话术不算知识点

-----------------------------
【当前知识点识别规则】
{strategy}
-----------------------------

【章节标题】
{chapter_title}

【章节正文全文】
{chapter_text}

-----------------------------
【输出要求】（必须严格按JSON数组输出）

[
  {{
    "knowledge_type": "操作步骤 / 异常处理 / 数据标准",
    "knowledge_text": "正文中的原文知识片段",
    "reason": "为什么它符合规则"
    "title": "所属最近标题名称"
  }}
]
如果没有符合的知识点，输出 []
"""

WORD_CHAPTER_KNOWLEDGE_PROMPT_EN = """
You are an 【Industrial Knowledge Point Identification Assistant】, specialized in identifying “explicit knowledge points that can be used for exam questions” from sections of operational documents.

I will provide the full body text of a chapter.

Your task is:
According to the specified 【Knowledge Point Identification Rules】, identify all knowledge points in the text that meet the rules.

⚠ Notes:

Only judge based on the content of this chapter

The knowledge must be explicit and directly usable for creating exam questions

Each knowledge point must be a sentence or a short paragraph quoted from the original text

Background explanations, purpose descriptions, and principle-based statements do NOT count as knowledge points

【Current Knowledge Point Identification Rules】
{strategy}

【Chapter Title】
{chapter_title}

【Full Chapter Text】
{chapter_text}

【Output Requirements】 (Must be strictly in JSON array format)

[
    {{
    "knowledge_type": "Operational Step / Abnormal Handling / Data Standard",
    "knowledge_text": "Original knowledge snippet from the text",
    "reason": "Why it meets the rule",
    "title": "The nearest associated section heading"
    }}
]

If no knowledge points meet the criteria, output: []
"""

WORD_CHAPTER_KNOWLEDGE_PROMPT_TH = """
คุณคือผู้ช่วยด้าน【การระบุจุดความรู้อุตสาหกรรม】ที่เชี่ยวชาญในการค้นหา “จุดความรู้ที่ชัดเจนและสามารถนำไปออกข้อสอบได้” จากเนื้อหาในเอกสารการปฏิบัติงานตามแต่ละบท

ฉันจะให้เนื้อหาฉบับเต็มของบทหนึ่งบท

หน้าที่ของคุณคือ:
ตาม【กฎการระบุจุดความรู้】ที่กำหนด ให้ค้นหาจุดความรู้ทั้งหมดในเนื้อหาที่ตรงตามกฎ

⚠ ข้อควรระวัง:

พิจารณาเฉพาะเนื้อหาในบทนี้เท่านั้น

ต้องเป็นความรู้ที่ ชัดเจนและสามารถนำไปออกข้อสอบได้โดยตรง

จุดความรู้แต่ละข้อ ต้องเป็นประโยคหรือย่อหน้าสั้น ๆ ที่ยกมาจากต้นฉบับ

คำอธิบายพื้นหลัง วัตถุประสงค์ หรือข้อความเชิงหลักการ จะไม่ถือว่าเป็นจุดความรู้

【กฎการระบุจุดความรู้ปัจจุบัน】
{strategy}

【ชื่อบท】
{chapter_title}

【เนื้อหาบทฉบับเต็ม】
{chapter_text}

【รูปแบบผลลัพธ์】 (ต้องส่งออกเป็นรูปแบบ JSON array เท่านั้น)

[
    {{
    "knowledge_type": "ขั้นตอนการปฏิบัติงาน / การจัดการกรณีผิดปกติ / มาตรฐานข้อมูล",
    "knowledge_text": "ข้อความความรู้จากต้นฉบับ",
    "reason": "เหตุผลว่าทำไมจึงตรงตามกฎ",
    "title": "ชื่อหัวข้อย่อยที่ใกล้ที่สุด"
    }}
]

หากไม่พบจุดความรู้ที่ตรงตามเงื่อนไข ให้ส่งออก: []
"""


GENERATE_WORD_CHAPTER_MULTI_QA_PROMPT = """
你是一名【工业培训考试出题专家】，擅长基于作业文档章节内容与多个指定知识点生成贴近真实现场的考试题目。

我会提供 3 部分信息：
1. 出题策略总体要求  
2. 本章节的标题  
3. 本章节中识别出的【多个知识点列表】

你的任务是：
针对每一个知识点，各生成一道考试题，所有题目必须符合题目规范。

--------------------------------
【章节标题】
{chapter_title}
--------------------------------

【章节背景正文】（用于题干场景，不是直接抄写来源）
{chapter_text}
--------------------------------

【本章节知识点列表】（每个知识点都要出题）
{knowledge_list_json}
--------------------------------

【题目生成硬性规则】

【题型限制】  
只能生成以下两种题型之一：
- 问答题
- 填空题

不允许生成选择题、判断题、多选题等其它题型

【题干必须自包含（Self-contained）】  
题目中**严禁**出现指代不明的词汇：
- 禁止：本章节、上文、本段、上述内容、该标题 等
- 题目必须让考生在不看到文档的情况下也能理解

【题干生成要求】
- 每一道题必须严格围绕“对应知识点内容”出题，不得混用多个知识点
- 要结合章节中的作业场景、设备、对象、流程、角色等信息
- 可以适度利用标题提供场景（例如：在进行落球试验前检查时…）
- 不要照抄知识点原句，要改写成考试表达
- 不要编造正文中不存在的场景

--------------------------------
【答案规范】

问答题：
- 提炼 1~4 个关键要点，作为答案
- 内容必须 100% 来自原文，不允许模型自行发挥

填空题：
- 题干中必须且只能出现一个填空占位符： ______  
- 该占位符必须替代“答案本身”，而不是出现在句尾当作提示  
- 填空题题干必须是“陈述句 + 缺失信息”，不能是疑问句  

难度因子：
- 简单：0.0 ~ 0.3
- 中等：0.4 ~ 0.6
- 困难：0.7 ~ 1.0

--------------------------------
【输出格式】

⚠ 仅输出严格 JSON 数组，不要输出 Markdown 代码块，不要输出任何解释文字

每个知识点输出一个对象，字段固定为英文 key：
- question: 题干文本
- question_type: 题型枚举，仅允许 short_answer 或 fill_in_the_blank
- answer: 若为 short_answer，必须是字符串数组；若为 fill_in_the_blank，必须是字符串
- difficulty_factor: 0~1 数值

示例：
[
  {{
    "question": "在设备启动前应完成哪些检查？",
    "question_type": "short_answer",
    "answer": ["检查润滑系统", "检查紧固件"],
    "difficulty_factor": 0.5
  }},
  {{
    "question": "设备正常运行时压力应保持在 ______。",
    "question_type": "fill_in_the_blank",
    "answer": "0.4~0.6 MPa",
    "difficulty_factor": 0.3
  }}
]
"""

GENERATE_WORD_CHAPTER_MULTI_QA_PROMPT_EN = """
ou are an 【Industrial Training Exam Question Expert】, skilled at generating realistic, field-oriented exam questions based on chapter content from operational documents and multiple specified knowledge points.

I will provide 3 parts of information:

Overall question strategy requirements

The chapter title

A list of multiple knowledge points identified in this chapter

Your task is:
For each knowledge point, generate one exam question. All questions must follow the required question rules.

【Chapter Title】
{chapter_title}
【Chapter Background Text】 (Used to enrich the scenario, not for direct copying)
{chapter_text}
【Knowledge Point List for This Chapter】 (Each knowledge point must have a question)
{knowledge_list_json}

【Hard Rules for Question Generation】

【Allowed Question Types】
Only one of the following two types may be generated:

Short-answer question

Fill-in-the-blank question

Do NOT generate multiple choice, true/false, or any other types.

【The Question Must Be Self-contained】
The question must NOT contain unclear references such as:
“this chapter”, “above”, “this paragraph”, “the above content”, “this title”, etc.
The question must be understandable without seeing the original document.

【Question Stem Requirements】

Each question must strictly focus on its corresponding knowledge point. Do NOT mix multiple knowledge points in one question

Incorporate the operational context from the chapter, such as scenario, equipment, objects, processes, and roles

You may appropriately use the title to help form the scenario (e.g., “Before conducting the drop test inspection…”)

Do not copy the original knowledge sentence directly; rewrite it into exam-style wording

Do not fabricate scenarios that do not exist in the text

【Answer Rules】

For short-answer questions:

Extract 1–4 key points as the answer

The content must come 100% from the original text, with no added invention

For fill-in-the-blank questions:

The question must contain exactly one blank placeholder: ______

The blank must replace the answer itself, not appear at the end as a hint

The stem must be a statement with missing information, NOT a question sentence

Difficulty factor:

Easy: 0.0 ~ 0.3

Medium: 0.4 ~ 0.6

Hard: 0.7 ~ 1.0

【Output Format】

Output strictly as a JSON array only. Do not output Markdown code fences. Do not output any explanation text.

For each knowledge point, output one object with fixed English keys:
- question: question stem text
- question_type: enum, only short_answer or fill_in_the_blank
- answer: for short_answer it must be a string array; for fill_in_the_blank it must be a string
- difficulty_factor: numeric value between 0 and 1

Example:
[
  {{
    "question": "What checks are required before starting the machine?",
    "question_type": "short_answer",
    "answer": ["Check lubrication system", "Inspect fasteners"],
    "difficulty_factor": 0.5
  }},
  {{
    "question": "Normal operating pressure should remain at ______.",
    "question_type": "fill_in_the_blank",
    "answer": "0.4~0.6 MPa",
    "difficulty_factor": 0.3
  }}
]
"""

GENERATE_WORD_CHAPTER_MULTI_QA_PROMPT_TH = """
คุณคือผู้เชี่ยวชาญด้าน【การออกข้อสอบฝึกอบรมอุตสาหกรรม】ที่มีความสามารถในการสร้างข้อสอบเสมือนจริงจากเนื้อหาในเอกสารการปฏิบัติงานระดับบท และจากจุดความรู้หลายรายการที่กำหนด

ฉันจะให้ข้อมูล 3 ส่วน:

ข้อกำหนดกลยุทธ์การออกข้อสอบโดยรวม

ชื่อบท

รายการจุดความรู้หลายรายการที่ตรวจพบในบทนี้

หน้าที่ของคุณคือ:
สำหรับ แต่ละจุดความรู้ ให้สร้าง ข้อสอบ 1 ข้อ โดยทุกข้อสอบต้องเป็นไปตามกฎที่กำหนด

【ชื่อบท】
{chapter_title}
【เนื้อหาพื้นหลังของบท】 (ใช้สร้างบริบท ไม่ใช่คัดลอกตรง ๆ)
{chapter_text}
【รายการจุดความรู้ของบทนี้】 (ทุกจุดความรู้ต้องมีข้อสอบ)
{knowledge_list_json}

【กฎบังคับในการสร้างข้อสอบ】

【ประเภทข้อสอบที่อนุญาต】
สามารถสร้างได้เพียงประเภทใดประเภทหนึ่งเท่านั้น:

ข้อสอบแบบอัตนัย (ตอบสั้น)

ข้อสอบแบบเติมคำในช่องว่าง

ห้ามสร้างข้อสอบแบบปรนัย ถูก/ผิด หรือประเภทอื่นใด

【โจทย์ต้องเข้าใจได้ด้วยตัวเอง】
ห้ามใช้คำอ้างอิงที่ไม่ชัดเจน เช่น
“บทนี้”, “ด้านบน”, “ย่อหน้านี้”, “เนื้อหาข้างต้น”, “หัวข้อนี้” เป็นต้น
ผู้สอบต้องเข้าใจโจทย์ได้โดยไม่ต้องเห็นเอกสารต้นฉบับ

【ข้อกำหนดการเขียนโจทย์】

แต่ละข้อสอบต้องอิงกับ “จุดความรู้ที่กำหนดให้ข้อนั้นเท่านั้น” ห้ามนำหลายจุดความรู้มาปนกัน

ต้องผสานบริบทการทำงานจากบท เช่น สถานการณ์ อุปกรณ์ วัตถุ กระบวนการ หรือบทบาท

สามารถใช้ชื่อบทช่วยสร้างสถานการณ์ได้อย่างเหมาะสม (เช่น “ก่อนเริ่มการทดสอบการตกกระแทก…”)

ห้ามคัดลอกประโยคความรู้เดิมตรง ๆ ต้องเขียนใหม่ในรูปแบบข้อสอบ

ห้ามแต่งสถานการณ์ที่ไม่มีอยู่ในเนื้อหา

【หลักเกณฑ์คำตอบ】

ข้อสอบแบบอัตนัย:

สรุปคำตอบเป็นประเด็นสำคัญ 1–4 ข้อ

เนื้อหาคำตอบต้องมาจากต้นฉบับ 100% ห้ามแต่งเพิ่ม

ข้อสอบแบบเติมคำ:

ในโจทย์ต้องมีช่องว่างเพียงหนึ่งตำแหน่ง: ______

ช่องว่างต้องแทนคำตอบโดยตรง ไม่ใช่วางท้ายประโยคเป็นคำใบ้

โจทย์ต้องเป็นประโยคบอกเล่าที่ข้อมูลหายไป ไม่ใช่ประโยคคำถาม

ระดับความยาก:

ง่าย: 0.0 ~ 0.3

ปานกลาง: 0.4 ~ 0.6

ยาก: 0.7 ~ 1.0

【รูปแบบผลลัพธ์】

ต้องส่งออกเป็น JSON array เท่านั้น ห้ามใช้ Markdown code block และห้ามมีคำอธิบายเพิ่มเติม

สำหรับแต่ละจุดความรู้ ให้ส่งออก 1 object โดยใช้ key ภาษาอังกฤษคงที่:
- question: ข้อความโจทย์
- question_type: ค่าที่อนุญาตมีเพียง short_answer หรือ fill_in_the_blank
- answer: ถ้าเป็น short_answer ต้องเป็นอาร์เรย์ของสตริง, ถ้าเป็น fill_in_the_blank ต้องเป็นสตริง
- difficulty_factor: ตัวเลขช่วง 0~1

ตัวอย่าง:
[
  {{
    "question": "ก่อนเริ่มเดินเครื่องต้องตรวจสอบอะไรบ้าง?",
    "question_type": "short_answer",
    "answer": ["ตรวจสอบระบบหล่อลื่น", "เช็คตัวยึดให้แน่น"],
    "difficulty_factor": 0.5
  }},
  {{
    "question": "แรงดันขณะเครื่องทำงานปกติควรอยู่ที่ ______",
    "question_type": "fill_in_the_blank",
    "answer": "0.4~0.6 MPa",
    "difficulty_factor": 0.3
  }}
]
"""
