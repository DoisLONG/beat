# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

"""
操作规程问答对生成提示词模板
用于操作规程类文件的多语言提示词管理
"""

# ========================= 中文提示词模板 =========================
universal_word_knowledge_prompt_zh="""
你是一名【知识点识别助手】，擅长从作业文档章节中识别“具备独立可考核价值的知识点”。
我会提供一个完整章节的正文内容（来自 Word 文档）。
你的任务是：
基于“是否可以独立形成一道可判分题目”这一标准，从正文中提取所有明确知识点。

【核心判断标准】
一个内容可以被认定为知识点，必须满足：
1.表达清晰、客观、可判断,存在明确的对错标准或验证依据
2.可以单独形成一道题目（填空题、问答题）
3.不依赖额外背景解释即可被理解和考核

【判断唯一标准】
该内容是否具备“独立可考核性”。

【执行要求】
1.只依据当前章节内容判断
2.每个知识点必须是正文中的一句或一小段原文（不得改写）
3.若同一段中包含多个可独立考核的信息，应拆分提取
4.必须标注其所属最近层级标题
5.若没有符合条件的内容，返回空数组 []

【章节标题】
{chapter_title}

【章节正文全文】
{chapter_text}

【输出要求】（必须严格按JSON数组输出）
[
    {{
        "knowledge_type": "自主识别",
        "knowledge_text": "正文中的原文知识片段",
        "reason": "该内容为何具备独立可考核性",
        "title": "所属最近标题名称"
    }}
]
"""


MAKE_OPERATION_QA_PROMPT_ZH = """
你是一名【培训考试出题专家】，擅长基于作业文档章节内容与多个指定知识点生成贴近真实现场的考试题目。

我会提供 3 部分信息：
1. 出题策略总体要求  
2. 本章节的标题  
3. 本章节中识别出的【多个知识点列表】

你的任务是：
针对每一个知识点，各生成一道考试题，所有题目必须符合题目规范

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


# ========================= 英文提示词模板 =========================

universal_word_knowledge_prompt_en="""
You are an industrial knowledge point identification assistant. You are good at identifying knowledge points with independent assessment value from a chapter of an operating procedure document.
I will provide the full body text of one chapter from a Word document.
Your task is:
Based on whether the content can independently become a gradable exam question, extract all explicit knowledge points from the chapter text.

【Core Criteria】
A piece of content can be treated as a knowledge point only if it:
1. Is clearly expressed, objective, and judgeable, with an explicit correctness standard or verification basis
2. Can independently form one exam question, such as a fill-in-the-blank or short-answer question
3. Can be understood and assessed without relying on extra background explanation

【Single Judgment Standard】
Whether the content has independent assessability.

【Execution Requirements】
1. Judge only based on the current chapter content
2. Each knowledge point must be an original sentence or a short original passage from the chapter text, without paraphrasing
3. If one paragraph contains multiple independently assessable pieces of information, split them out separately
4. Mark the nearest heading each knowledge point belongs to
5. If nothing qualifies, return an empty array []
6. The total number of knowledge points must be less than 10

【Chapter Title】
{chapter_title}

【Full Chapter Text】
{chapter_text}

【Output Requirement】(must be strict JSON array output)
[
    {{
        "knowledge_type": "Self-identified",
        "knowledge_text": "Original knowledge snippet from the chapter text",
        "reason": "Why this content has independent assessability",
        "title": "Nearest heading title"
    }}
]
"""

MAKE_OPERATION_QA_PROMPT_EN = """
You are an industrial training exam question design expert. You are good at generating realistic exam questions based on a chapter of an operating procedure document and a list of identified knowledge points.

I will provide 3 parts of information:
1. The chapter title
2. The chapter background text
3. A list of multiple identified knowledge points from this chapter

Your task is:
Generate exactly one exam question for each knowledge point. Every question must follow the rules below.

--------------------------------
【Chapter Title】
{chapter_title}
--------------------------------

【Chapter Background Text】(used for scenario context, not for direct copying)
{chapter_text}
--------------------------------

【Knowledge Point List】(every knowledge point must be covered)
{knowledge_list_json}
--------------------------------

【Hard Rules】

【Allowed Question Types】
Only these two types are allowed:
- Short-answer question
- Fill-in-the-blank question

Do not generate multiple choice, true/false, or any other types.

【Self-contained Question Stem】
The question must not contain ambiguous references such as:
- this chapter, above, this paragraph, the above content, this title
- The learner must be able to understand the question without seeing the source document

【Question Writing Requirements】
- Each question must focus on only one corresponding knowledge point
- Use the work scenario, equipment, objects, processes, or roles from the chapter when helpful
- You may use the title to provide context
- Do not copy the original knowledge text directly; rewrite it into exam-style wording
- Do not invent scenarios that do not exist in the chapter
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

Difficulty factor:
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


# ========================= 泰文提示词模板 =========================

universal_word_knowledge_prompt_th="""
คุณคือผู้ช่วยระบุจุดความรู้ด้านอุตสาหกรรมที่เชี่ยวชาญในการค้นหาจุดความรู้ที่มีคุณค่าในการประเมินอย่างอิสระจากเนื้อหาของแต่ละบทในเอกสารขั้นตอนการปฏิบัติงาน
ฉันจะให้เนื้อหาฉบับเต็มของหนึ่งบทจากเอกสาร Word
หน้าที่ของคุณคือ:
พิจารณาจากเกณฑ์ว่าเนื้อหานั้นสามารถนำไปสร้างเป็นข้อสอบที่ให้คะแนนได้อย่างอิสระหรือไม่ แล้วดึงจุดความรู้ที่ชัดเจนทั้งหมดออกมาจากเนื้อหาบทนั้น

【เกณฑ์หลัก】
เนื้อหาหนึ่งจะถือเป็นจุดความรู้ได้ก็ต่อเมื่อ:
1. มีการสื่อสารอย่างชัดเจน เป็นข้อเท็จจริง และสามารถตัดสินได้ โดยมีเกณฑ์ความถูกต้องหรือหลักฐานตรวจสอบที่ชัดเจน
2. สามารถสร้างเป็นข้อสอบเดี่ยวได้ เช่น ข้อเติมคำหรือข้อถาม-ตอบ
3. สามารถเข้าใจและประเมินได้โดยไม่ต้องอาศัยคำอธิบายพื้นหลังเพิ่มเติม

【เกณฑ์การตัดสินเพียงข้อเดียว】
เนื้อหานั้นมีคุณสมบัติในการประเมินอย่างอิสระหรือไม่

【ข้อกำหนดในการดำเนินการ】
1. พิจารณาเฉพาะจากเนื้อหาในบทปัจจุบันเท่านั้น
2. แต่ละจุดความรู้ต้องเป็นประโยคต้นฉบับหรือข้อความสั้นจากเนื้อหาเดิม ห้ามเรียบเรียงใหม่
3. หากย่อหน้าเดียวมีหลายข้อมูลที่สามารถประเมินแยกกันได้ ให้แยกออกมาเป็นหลายจุด
4. ต้องระบุหัวข้อที่ใกล้ที่สุดซึ่งจุดความรู้นั้นสังกัดอยู่
5. หากไม่มีเนื้อหาที่เข้าเกณฑ์ ให้คืนค่าเป็นอาร์เรย์ว่าง []
6. จำนวนจุดความรู้ทั้งหมดต้องน้อยกว่า 10

【ชื่อบท】
{chapter_title}

【เนื้อหาฉบับเต็มของบท】
{chapter_text}

【รูปแบบผลลัพธ์】(ต้องส่งออกเป็น JSON array อย่างเคร่งครัด)
[
    {{
        "knowledge_type": "ระบุอัตโนมัติ",
        "knowledge_text": "ข้อความต้นฉบับที่เป็นจุดความรู้จากเนื้อหา",
        "reason": "เหตุผลว่าทำไมเนื้อหานี้จึงสามารถประเมินได้อย่างอิสระ",
        "title": "ชื่อหัวข้อที่ใกล้ที่สุด"
    }}
]
"""

MAKE_OPERATION_QA_PROMPT_TH = """
คุณคือผู้เชี่ยวชาญด้านการออกข้อสอบสำหรับการฝึกอบรมอุตสาหกรรม โดยเชี่ยวชาญในการสร้างข้อสอบจากเนื้อหาของเอกสารขั้นตอนการปฏิบัติงานและรายการจุดความรู้ที่ระบุไว้

ฉันจะให้ข้อมูล 3 ส่วน:
1. ชื่อบท
2. เนื้อหาพื้นหลังของบท
3. รายการจุดความรู้หลายข้อที่ระบุจากบทนี้

หน้าที่ของคุณคือ:
สร้างข้อสอบ 1 ข้อต่อ 1 จุดความรู้ โดยทุกข้อจะต้องเป็นไปตามข้อกำหนดด้านล่าง

--------------------------------
【ชื่อบท】
{chapter_title}
--------------------------------

【เนื้อหาพื้นหลังของบท】(ใช้เป็นบริบทของโจทย์ ไม่ใช่สำหรับคัดลอกตรง)
{chapter_text}
--------------------------------

【รายการจุดความรู้】(ทุกจุดความรู้ต้องถูกนำไปออกข้อสอบ)
{knowledge_list_json}
--------------------------------

【กฎบังคับ】

【ประเภทข้อสอบที่อนุญาต】
อนุญาตเฉพาะ 2 ประเภทนี้เท่านั้น:
- ข้อถาม-ตอบ
- ข้อเติมคำ

ห้ามสร้างข้อเลือกตอบ ข้อถูกผิด หรือรูปแบบอื่นใด

【โจทย์ต้องเข้าใจได้ด้วยตัวเอง】
ในโจทย์ห้ามมีคำอ้างอิงที่ไม่ชัดเจน เช่น:
- บทนี้, ข้างต้น, ย่อหน้านี้, เนื้อหาข้างต้น, หัวข้อนี้
- ผู้เข้าสอบต้องเข้าใจโจทย์ได้แม้ไม่เห็นเอกสารต้นฉบับ

【ข้อกำหนดในการเขียนโจทย์】
- แต่ละข้อจะต้องอิงกับจุดความรู้ที่สอดคล้องกันเพียงข้อเดียว
- สามารถใช้บริบทของงาน อุปกรณ์ วัตถุ กระบวนการ หรือบทบาทจากบทนั้นได้
- สามารถใช้ชื่อบทช่วยสร้างบริบทได้
- ห้ามคัดลอกข้อความจุดความรู้ตรง ๆ ให้ปรับเป็นสำนวนข้อสอบ
- ห้ามแต่งสถานการณ์ที่ไม่มีอยู่จริงในบท
- เนื้อหาโจทย์และคำตอบต้องเขียนเป็นภาษาไทยเท่านั้น

--------------------------------
【ข้อกำหนดของคำตอบ】

ข้อถาม-ตอบ:
- สรุปคำตอบเป็น 1 ถึง 4 ประเด็นสำคัญ
- เนื้อหาคำตอบต้องมาจากต้นฉบับ 100%

ข้อเติมคำ:
- ในโจทย์ต้องมีช่องว่างเพียง 1 ตำแหน่งเท่านั้น: ______
- ช่องว่างต้องแทนคำตอบโดยตรง ไม่ใช่วางไว้ท้ายประโยคเพื่อเป็นคำใบ้
- โจทย์ต้องเป็นประโยคบอกเล่าที่มีข้อมูลหายไป ไม่ใช่ประโยคคำถาม

ค่าความยาก:
- ง่าย: 0.0 ~ 0.3
- ปานกลาง: 0.4 ~ 0.6
- ยาก: 0.7 ~ 1.0

--------------------------------
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

# ========================= 背景故事生成提示词模板 =========================
BACKSTORY_GENERATE_PROMPT_WORD_ZH="""
你是一位专业的操作规程文档分析专家。请根据以下操作规程片段内容，提炼出一段简明扼要的背景介绍，便于后续问答对补充背景信息。
要求：
1. 仅输出背景描述文本，不要包含任何额外说明或注释
2. 不要丢失 内容细节，尽可能详细
3. 字数在100字左右
4. 用连贯的段落形式表达，不要使用列表或分项
【操作规程片段内容】
{row}
"""

BACKSTORY_GENERATE_PROMPT_WORD_EN="""
You are a professional operating procedure document analysis expert. Based on the following excerpt from an operating procedure, please extract a concise and clear background introduction that can be used to supplement contextual information for subsequent question-and-answer generation.
Requirements:
1. Output only the background description text without any additional explanations or comments.
2. Do not lose content details; be as detailed as possible.
3. Approximately 100 words.
4. Express in coherent paragraph form without using lists or bullet points.
【Procedure Excerpt】
{row}
"""

BACKSTORY_GENERATE_PROMPT_WORD_TH="""
คุณเป็นผู้เชี่ยวชาญด้านการวิเคราะห์เอกสารขั้นตอนการปฏิบัติงาน โปรดสกัดข้อมูลพื้นหลังโดยสรุปอย่างกระชับและชัดเจนจากเนื้อหาบางส่วนของคู่มือขั้นตอนการปฏิบัติงานต่อไปนี้ เพื่อใช้เป็นบริบทเสริมสำหรับการสร้างชุดคำถามและคำตอบในขั้นตอนถัดไป
ข้อกำหนด:
1. ให้ผลลัพธ์เป็นข้อความคำอธิบายพื้นหลังเท่านั้น โดยไม่ต้องมีคำอธิบายหรือความคิดเห็นเพิ่มเติมใดๆ
2. อย่าทำให้รายละเอียดของเนื้อหาหายไป ให้ละเอียดที่สุดเท่าที่จะเป็นไปได้
3. ประมาณ 100 คำ
4. แสดงในรูปแบบย่อหน้าที่สอดคล้องกันโดยไม่ใช้รายการหรือจุดบูลเล็ต
【บทคัดย่อของขั้นตอน】
{row}
"""
