# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

# 提示词管理文件
# 按功能模块组织所有提示词，便于统一管理和维护


# ==================== 重复项识别提示词 ====================

def get_duplicate_detection_instruction(lang: str = "zh") -> str:
    """获取重复项识别的指令提示词"""
    if lang == "en":
        return (
            "You are a semantic deduplication assistant. Please classify questions with the same or highly similar meanings.\n"
            "【Judgment Rules】\n"
            "1. The question types must be consistent (Q&A/Fill-in-the-blank cannot be confused).\n"
            "2. **Core Requirement**: If the questions are the same but one of the answers is logically incorrect (e.g., asking for time but answering with status), "
            "you must choose the most logically correct and matching question as the representative."
        )
    if lang == "th":
        # Thai translation
        return (
            "คุณคือผู้ช่วยในการลบข้อมูลซ้ำเชิงความหมาย โปรดจัดหมวดหมู่คำถามที่มีความหมายเหมือนกันหรือคล้ายกันอย่างมาก\n"
            "【กฎการตัดสิน】\n"
            "1. ประเภทของคำถามต้องสอดคล้องกัน (คำถาม-คำตอบ/เติมคำในช่องว่างไม่สามารถสับสนกันได้)\n"
            "2. **ข้อกำหนดหลัก**: หากคำถามเหมือนกันแต่คำตอบหนึ่งมีตรรกะที่ผิด (เช่น ถามเวลาแต่ตอบสถานะ) "
            "คุณต้องเลือกคำถามที่มีตรรกะถูกต้องที่สุดและตรงกับคำถามเป็นตัวแทน"
        )
    else:
        return (
            "你是一个语义去重助手。请将意思相同或极度相似的题目归类。\n"
            "【判定规则】\n"
            "1. 题型必须一致（问答题/填空题不可混淆）。\n"
            "2. **核心要求**：如果题目相同，但其中一项答案逻辑错误（例如问时间却回答状态），"
            "必须选择逻辑最正确、与问法最匹配的一项作为代表（Representative）。"
        )

def get_duplicate_detection_prompt(instruction: str, questions_text: str) -> str:
    """获取重复项识别的完整提示词"""
    return f"""{instruction}

    输出格式 - NDJSON】
    - 仅输出纯文本 NDJSON，每行一条。
    - 格式：r:<代表项索引>|g:<所有重复项索引，逗号分隔>
    
    示例：
    r:0|g:0,2
    r:15|g:15,43
    
    【数据】
    {questions_text}
    """


# ==================== 操作规程文档分析提示词 ====================

def get_operation_manual_background_prompt(filename: str, row: str, lang: str = "zh") -> str:
    """获取操作规程文档分析的背景生成提示词"""
    if lang.lower() == "en":
        return (
            f"You are a professional procedure document analysis expert. Please extract a concise background introduction based on the following excerpt from the \"{filename}\" procedure document, to facilitate supplementing background information for subsequent Q&A pairs.\n"
            "Requirements:\n"
            "1. Only output background description text, do not include any additional explanations or comments\n"
            "2. Do not lose content details, be as detailed as possible\n"
            "3. Around 100 words\n"
            "4. Express in a coherent paragraph form, do not use lists or items\n"
            f"\n【Procedure Document Excerpt】\n{row}\n"
        )
    elif lang.lower() == "th":
        return (
            f"คุณเป็นผู้เชี่ยวชาญในการวิเคราะห์เอกสารขั้นตอนการปฏิบัติงาน โปรดสรุปคำแนะนำ배경ที่กระชับตามส่วนย่อของเอกสารขั้นตอนการปฏิบัติงาน \"{filename}\" ด้านล่างเพื่ออำนวยความสะดวกในการเพิ่มข้อมูล배경สำหรับคู่ถาม-ตอบในภายหลัง\n"
            "要求:\n"
            "1. 仅输出背景描述文本，不要包含任何额外说明或注释\n"
            "2. 不要丢失 内容细节，尽可能详细\n"
            "3. 字数在100字左右\n"
            "4. 用连贯的段落形式表达，不要使用列表或分项\n"
            f"\n【操作规程片段内容】\n{row}\n"
        )
    else:
        return (
            f"你是一位专业的操作规程文档分析专家。请根据以下《{filename}》操作规程片段内容，提炼出一段简明扼要的背景介绍，便于后续问答对补充背景信息。\n"
            "要求：\n"
            "1. 仅输出背景描述文本，不要包含任何额外说明或注释\n"
            "2. 不要丢失 内容细节，尽可能详细\n"
            "3. 字数在100字左右\n"
            "4. 用连贯的段落形式表达，不要使用列表或分项\n"
            f"\n【操作规程片段内容】\n{row}\n"
        )

def get_operation_supplement_prompt(filename: str, existing_titles: set, need: int, row_to_text: callable, row: dict, user_prompt: str = "", lang: str = "zh", TOTAL_ROUNDS: int = 50) -> str:
    """获取操作规程补充问答生成提示词"""
    if lang.lower() == "en":
        prompt = (
            "You are an expert in generating supplementary Q&A for procedure documents.\n"
            f"The current number of questions is below the target of {TOTAL_ROUNDS}. This time, please add approximately {need} more questions.\n"
            "Requirements: Maintain a strict balance and alternation between Q&A and Fill-in-the-blank questions; do not repeat any existing questions; all answers must be derived from the original text or its paraphrases. If materials are insufficient, generate fewer.\n"
            "Do not output any explanations, statistics, or JSON outside of the question blocks. Each question should still include: 题目、题型、答案、难度因子\n"
            f"Existing question count: {len(existing_titles)} (no need to list).\n"
            f"Input Content:\n{row_to_text(row)}\n"
            f"Filename: {filename}\n"
        )
        if user_prompt:
            prompt += f"User Additional Requirements: {user_prompt}\n"
    elif lang.lower() == "th":
        prompt = (
            "คุณเป็นผู้เชี่ยวชาญด้านการสร้างคำถามและคำตอบเสริมสำหรับเอกสารขั้นตอนการปฏิบัติงาน\n"
            f"จำนวนคำถามปัจจุบันต่ำกว่าเป้าหมายที่ตั้งไว้ที่ {TOTAL_ROUNDS} ครั้งนี้คาดหวังที่จะเพิ่มคำถามประมาณ {need} ข้อ\n"
            "ข้อกำหนด: รักษาสมดุลและสลับกันอย่างเคร่งครัดระหว่างคำถาม-คำตอบและเติมคำในช่องว่าง; ห้ามทำซ้ำคำถามที่มีอยู่แล้ว; คำตอบทั้งหมดต้องมาจากข้อความต้นฉบับหรือการเขียนใหม่ในรูปแบบอื่น หากเนื้อหาไม่เพียงพอสามารถสร้างได้น้อยลง\n"
            "ห้ามส่งออกคำอธิบาย สถิติ หรือ JSON นอกเหนือจากบล็อกคำถาม แต่ละคำถามยังคงต้องมี: 题目、题型、答案、难度因子。\n"
            f"จำนวนคำถามที่มีอยู่: {len(existing_titles)} (ไม่จำเป็นต้องแสดงรายการ)\n"
            f"เนื้อหาอินพุต:\n{row_to_text(row)}\n"
            f"ชื่อไฟล์: {filename}\n"
        )
        if user_prompt:
            prompt += f"ข้อกำหนดเพิ่มเติมจากผู้ใช้: {user_prompt}\n"
    else:
        prompt = (
            "你是一位操作规程补充问答生成专家。\n"
            f"当前已有部分题目，总题量仍低于目标 {TOTAL_ROUNDS}，本次期望新增约 {need} 题。\n"
            "要求：新增题保持问答题与填空题数量严格相等并交替；题目不得与已存在题目重复；所有答案必须来源于原文或其同义改写。素材不足可少生成。\n"
            "禁止输出除题目块外的任何说明、统计或JSON。每题依旧包含：题目、题型、答案、难度因子。\n"
            f"已有题目数量：{len(existing_titles)}（无需列出）。\n"
            f"输入内容：\n{row_to_text(row)}\n"
            f"文件名：{filename}\n"
        )
        if user_prompt:
            prompt += f"用户补充要求：{user_prompt}\n"
    return prompt


# ==================== 应急预案演练问答提示词 ====================

def get_emergency_drill_prompt(section: dict, filename: str, section_to_text: callable, user_prompt: str = "", min_pairs: int = 1, total_items: int = 1, TOTAL_ROUNDS: int = 50) -> str:
    """获取应急预案演练问答生成提示词"""
    name = filename.split("/")[-1].rsplit(".", 1)[0]
    is_table = 'cells' in section
    data_type = "表格" if is_table else "章节"
    prompt = (
        f"你是应急预案演练问答生成专家。根据《{name}》的{data_type}内容生成高质量问答对。\n\n"
        "【总体目标】\n"
        f"整份文件期望总题数不少于 {TOTAL_ROUNDS}。当前共有 {total_items} 个有效{data_type if total_items == 1 else '单元'}，本{data_type}需至少生成 M 组题（M={min_pairs}），每组=1问答题+1填空题，总计 2×M 题。若素材不足无法达到 M 组，取实际可配对最大组数 K；K=0 则不输出任何题目。\n\n"
        "【题型与交替】\n"
        "1. 题型仅允许：问答题、填空题。输出必须严格按 问答题→填空题→问答题→填空题... 交替，数量严格相等。禁止出现连续两个同题型或数量不平衡。\n"
        "2. 生成流程：先内部枚举可做问答题素材集合，再枚举可做填空题素材集合（仅1个空 ______），取两集合最小值=K 作为可配对组数。若 K≥M 输出 M 组，否则输出 K 组。\n\n"
        "【答案规范】\n"
        "- 问答题答案：提炼1~4个关键要点，每行一个；内容必须 100% 来自原文，可做同义顺序微调，不得添加新信息。\n"
        "- 填空题：题干一个空（______），答案为原文出现的精确词语/短语/数值，不做解释。\n"
        "- 严禁使用'等'、'主要有'等模糊词。\n"
        "- 难度因子：简单(0~0.3)、中等(0.4~0.6)、困难(0.7~1.0) 要有分布。\n\n"
        "【优先出题方向】流程/时序/触发条件/决策逻辑；角色职责与协同；风险识别与控制措施；资源配置/调度；评估验证与改进。\n"
        "【禁止出题】纯人名/电话/地址/无内容空模板。\n"
    )
    prompt += f"\n【输入{data_type}】\n{section_to_text(section)}\n\n"
    if user_prompt:
        prompt += f"【补充要求】{user_prompt}\n\n"
    prompt += (
        "【输出格式示例】(仅示例，正式输出不重复示例)\n"
        f"题目：现场副总指挥在应急演练中的职责是什么？\n"
        "题型：问答题\n"
        "答案：\n"
        "协助总指挥对应急演练进行全面指挥\n"
        "指导各应急组有效开展应急处置工作\n"
        "保障应急演练工作的顺利开展\n"
        "及时向部门及公司上报事故\n"
        "难度因子：0.5\n\n"
        f"题目：对讲机的保养排期为______。\n"
        "题型：填空题\n"
        "答案：每月检查一次\n"
        "难度因子：0.2\n\n"
        "【输出要求】只输出题目块；每题之间空一行；不输出任何说明/统计/JSON；若无素材则直接返回空。\n"
    )
    return prompt

def get_emergency_drill_background_prompt(item: dict, filename: str) -> str:
    """获取应急预案演练背景生成提示词"""
    if 'content' in item:
        # 章节型
        title = item.get('title', '')
        content = item.get('content', '')
        return (
            f"你是一位专业的应急预案演练文档分析专家。请根据以下《{filename}》的“{title}”章节内容，提炼出一段简明扼要的背景介绍，便于后续问答对补充背景信息。\n"
            "要求：\n"
            "1. 仅输出背景描述文本，不要包含任何额外说明或注释\n"
            "2. 不要丢失内容细节，尽可能详细\n"
            "3. 字数在100字左右\n"
            "4. 用连贯的段落形式表达，不要使用列表或分项\n"
            f"\n【章节内容】\n标题：{title}\n内容：{content}\n"
        )
    elif 'cells' in item:
        # 表格型
        table_title = item.get('table_title', '')
        cells = item.get('cells', [])
        cells_text = '\n'.join([str(cell) for cell in cells if cell])
        return (
            f"你是一位专业的应急预案演练文档分析专家。请根据以下《{filename}》的“{table_title}”表格内容，提炼出一段简明扼要的背景介绍，便于后续问答对补充背景信息。\n"
            "要求：\n"
            "1. 仅输出背景描述文本，不要包含任何额外说明或注释\n"
            "2. 不要丢失内容细节，尽可能详细\n"
            "3. 字数在100字左右\n"
            "4. 用连贯的段落形式表达，不要使用列表或分项\n"
            "5. 如果表格内容无实质性信息，请直接返回空\n"
            f"\n【表格内容】\n表格名：{table_title}\n内容：{cells_text}\n"
        )
    else:
        return ""

def get_emergency_drill_supplement_prompt(item: dict, filename: str, existing_titles: set, need: int, section_to_text: callable, user_prompt: str = "", TOTAL_ROUNDS: int = 50) -> str:
    """获取应急预案演练补充问答生成提示词"""
    is_table = 'cells' in item
    data_type = "表格" if is_table else "章节"
    prompt = (
        f"你是应急预案演练补充问答生成专家。当前已有部分题目，总题量低于 {TOTAL_ROUNDS}，期望新增约 {need} 题。\n"
        f"本次仅针对该{data_type}补充，保持 问答题 与 填空题 数量相等并严格交替，不得与已有题目重复。素材不足可少生成。\n"
        "禁止输出除题目块外的任何说明或统计。\n"
        f"已有题目数量：{len(existing_titles)}（无需列出）。\n"
        f"输入{data_type}内容：\n{section_to_text(item)}\n"
        f"文件名：{filename}\n"
    )
    if user_prompt:
        prompt += f"补充要求：{user_prompt}\n"
    return prompt


# ==================== 通用问答生成提示词 ====================

def get_word_pdf_qa_prompt(item: dict, filename: str, row_to_text: callable, user_prompt: str = "", min_pairs: int = 1, total_items: int = 1, TOTAL_ROUNDS: int = 50) -> str:
    """获取通用问答生成提示词"""
    name = filename.split("/")[-1].rsplit(".", 1)[0]
    is_table = 'cells' in item
    data_type = "表格" if is_table else "章节"
    prompt = (
        f"你是专业的{data_type}问答生成专家。根据《{name}》的{data_type}内容尽可能多的生成高质量问答对。\n\n"
        "【总体目标】\n"
        f"整份文件期望总题数不少于 {TOTAL_ROUNDS}。当前共有 {total_items} 个有效{data_type}，本{data_type}需至少生成 M 组题（M={min_pairs}），每组=1问答题+1填空题，总计 2×M 题。\n"
        "若素材不足无法达到 M 组，取实际可配对最大组数 K；K=0 则不输出任何题目。\n\n"
        "【题型与交替】\n"
        "1. 题型仅允许：问答题、填空题。输出必须严格按 问答题→填空题→问答题→填空题... 交替。\n"
        "2. 生成流程：先枚举可做问答题素材集合，再枚举可做填空题素材集合，取两集合最小值=K 作为可配对组数。\n\n"
        "【答案规范】\n"
        "- 问答题答案：提炼1~4个关键要点，每行一个；内容必须 100% 来自原文。\n"
        "- 填空题：题干一个空 ______，答案为原文出现的精确词语/短语/数值。\n"
        "- 难度因子：简单(0~0.3)、中等(0.4~0.6)、困难(0.7~1.0)。\n\n"
        "【优先出题方向】流程/时序/触发条件/决策逻辑；角色职责与协同；风险识别与控制措施；资源配置/调度；评估验证与改进。\n"
        "【禁止出题】纯人名/电话/地址/无内容空模板。\n"
    )
    prompt += f"\n【输入{data_type}】\n{row_to_text(item)}\n\n"
    if user_prompt:
        prompt += f"【补充要求】{user_prompt}\n\n"
    prompt += (
        "【输出格式示例】\n"
        f"题目：在发生酸性灼伤事故时，现场急救的首要措施是？\\n\\n"
        "题型：问答题\n"
        "答案：\n"
        "1. 立即脱去被污染的衣物\n"
        "2. 用大量流动清水冲洗至少15分钟\n"
        "3. 及时就医\n"
        "难度因子：0.5\n\n"
        f"题目：实验室内的电气设备起火时，严禁使用______进行灭火。\n"
        "题型：填空题\n"
        "答案：水\n"
        "难度因子：0.2\n\n"
        "【输出要求】\n"
        "1.只输出题目块；每题之间空一行；\n"
        "2.题目必须结合行内的主要标识符（如名称、型号）进行提问。\n"
        "3.不输出任何说明。\n"
        "4.请直接输出结果，不要包含任何思考过程、分析过程或 <think>...</think> 标签。"
    )
    return prompt

def get_universal_background_prompt(filename: str, content: str, lang: str = "zh") -> str:
    """获取通用背景生成提示词"""
    if lang.lower() == "th":
        return (
            f"คุณเป็นผู้เชี่ยวชาญด้านการวิเคราะห์เอกสาร โปรดสกัดบทสรุปพื้นหลังแบบกระชับจากเนื้อหาใน 《{filename}》 เพื่อใช้เป็นข้อมูลประกอบในการสร้างชุดคำถาม\U00002014คำตอบต่อไป\n"
            "ข้อกำหนด:\n"
            "1. แสดงเฉพาะข้อความพื้นหลัง ไม่ต้องมีคำอธิบายหรือหมายเหตุเพิ่มเติม\n"
            "2. พยายามคงรายละเอียดให้มากที่สุด เท่าที่จำเป็นโดยไม่บิดเบือนเนื้อหา\n"
            "3. ความยาวประมาณ 100\U00002013 200 คำ\n"
            "4. ใช้รูปแบบย่อหน้าเดียวที่ต่อเนื่อง ห้ามใช้รายการหัวข้อหรือบูลเล็ต\n"
            "5. ส่งออกในรูปแบบ JSON: {\"background\": \"ข้อความพื้นหลัง\"}\n"
            f"\n【เนื้อหา】\n{content}\n"
        )

    if lang.lower() == "en":
        return (
            f"You are a professional document analysis expert. Please extract a brief background description from the following《{filename}》content, which will be used to supplement the background information for subsequent question-and-answer pairs. \n"
            "Requirements:\n"
            "1. Only output background description text, without any additional explanations or notes\n"
            "2. Do not lose content details, as much as possible\n"
            "3. The number of words should be between 100 and 200\n"
            "4. Use a continuous paragraph form to express, do not use lists or items\n"
            "5. Output in JSON format: {\"background\": \"your background text\"}\n"
            f"\n【Content】\n{content}\n"
        )
    else:
        return (
            f"你是一位专业的文档分析专家。请根据以下《{filename}》的内容，提炼出一段简明扼要的背景介绍，便于后续问答对补充背景信息。\n"
            "要求：\n"
            "1. 仅输出背景描述文本，不要包含任何额外说明或注释\n"
            "2. 不要丢失内容细节，尽可能详细\n"
            "3. 字数在100字左右\n"
            "4. 用连贯的段落形式表达，不要使用列表或分项\n"
            "5. 以JSON格式输出: {\"background\": \"背景描述文本\"}\n"
            f"\n【内容】\n{content}\n"
        )


# ==================== Excel表格结构识别提示词 ====================

def get_excel_header_detection_prompt(preview_text: str, lang: str = "zh") -> str:
    """获取Excel表格结构识别提示词"""
    if lang == "th":
        return f"""
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
    elif lang == "en":
        return f"""
                        You are an expert in data analysis and table structure recognition. 
                        Input: Excel preview content {preview_text}. It may contain multi-line headers, merged cells, and empty cells.

                        Your task:
                        Identify the final column headers (Heads) correctly from this preview content and output them as an array heads (in the order they appear).

                        ### Header Identification Rules:
                        1. If the upper header spans multiple columns but those columns have "sub-titles" in the next row, 
                           use only the sub-titles as column headers. **Do not** append the sub-titles to the main header.
                           Example:
                           Upper row: "Work Standards (Text)" (spanning 4 columns)
                           Lower row: "Work Steps", "Standards", "Risks", "Controls"
                           → Result must be 4 separate headers, not concatenated with the upper name

                        2. Text merging should only be done when there are merged cells in the "vertical" direction (same column but multiple lines). 
                           Join text with \n
                           Example: If a single header spans 2 rows in the same column, combine as "A\nB"

                        3. The final headers (Heads) must match the number of columns in the actual data rows.

                        Please return the result in the strict JSON format:
                        {{
                          "heads": ["Header1", "Header2", "Header3", ...],
                          "start_row": <int>,
                          "end_row": <int>
                        }}

                        Field details:
                        - heads: All column headers from left to right. If there are vertically merged cells, join with \n
                        - start_row, end_row: The start and end row numbers of the entire "header area" in Excel (starting from 1)
                        """
    else:
        return f"""
                    你是数据处理与表格结构识别专家。
                    输入：Excel 预览内容 {preview_text}，可能包含多行表头、合并单元格与空单元格。
                    任务：正确识别出最终的列头（Heads），并按出现顺序输出为数组。

                    【判定规则】
                    1. 若上方表头覆盖多列，但这些列在下方有“子标题”，
                       则仅以子标题作为列头，**禁止** 将子标题拼接在主标题后。
                       示例：
                       上层：“工作标准（文本）”（跨4列）
                       下层：“工作步骤”、“标准要求”、“风险”、“控制措施”
                       → 结果必须是4个独立列头，不可拼接上层名称

                    2. 仅当“纵向”合并单元格时（同一列多行）才进行文本合并，
                       用 \n 连接文本。
                       例如：某列头跨2行，合并为 "A\nB"

                    3. 最终列头（Heads）数量必须与真实数据列数一致。

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


# ==================== 风险识别问答提示词 ====================

def get_risk_qa_prompt(batch_text: str, filename: str, batch_idx: int, total_batches: int, user_prompt: str = "", min_pairs: int = 1, total_rows: int = 1, TOTAL_ROUNDS: int = 50) -> str:
    """获取风险识别多问答对生成提示词"""
    name = filename.split("/")[-1].rsplit(".", 1)[0]
    prompt = (
        "你是一位专业的安全风险问答对生成专家，请严格遵守以下规范：\\n\\n"
        "【总体生成目标】\\n"
        f"系统期望全文件合计不少于 {TOTAL_ROUNDS} 道题（单题计数），当前共 {total_rows} 行风险识别数据。请在保证质量的前提下充分挖掘本行内容以贡献足够题量。\\n\\n"
        "【任务目标】\\n"
        f"基于提供的风险识别内容，从多个字段生成高质量问答对。每个字段充分挖掘，信息越充分题量越多；信息单薄或无实际要点的字段跳过，不生成低价值题目。\\n\\n"
        "【最低题量要求】\\n"
        f"本行必须至少生成 M 组题目（M={min_pairs}），每组包含 1 道问答题 + 1 道填空题，共 2×M 道题，严格按 问答题→填空题 交替。若素材不足无法满足 M 组，则取可配对素材的最大组数 K，同时保持两类题目数量相等。若 K=0 则不输出任何题目。\\n\\n"
        "【题型与配对总则】\\n"
        "1. 题型只允许：问答题、填空题。填空题题干仅允许一个空（______）。\\n"
        "2. ‘问答题’与‘填空题’数量必须严格相等，并按“问答题→填空题→问答题→填空题...”交替排列输出。绝不允许数量不等或连续出现两个同题型。\\n"
        "3. 生成流程：先枚举可做问答题素材集合与填空题素材集合，计算最小可配对数；若小于设定的 M，则使用实际可配对数。\\n"
        "4. 不要输出任何解释、统计、总结或 JSON。只输出题目块。\\n"
        "5. 每题必须包含：题目、题型、答案、难度因子、来源字段。\\n"
        "7. 答案必须来自原文或其等价改写（同义/语序调整），禁止臆造。\\n"
        "8. 问答题答案：列出1~4个关键要点，分行或分号。填空题答案：原文中出现的明确词或短语，不做解释。\\n"
        "9. 难度因子分布：简单(0~0.3)、中等(0.4~0.6)、困难(0.7~1.0)，整体需有区分。\\n"
        "10. 内部自检：若交替或数量不平衡应重新组织，直至符合。\\n"
        "11. 禁止出现‘示例’‘范例’‘如下’等词。\\n\\n"
        "【字段与题型映射】\\n"
        "问答题来源字段：事故案例收集、风险因素描述、风险控制措施-消除、风险控制措施-消减或替代、风险控制措施-工程防呆、风险控制措施-管理控制、风险控制措施-个人防护\\n"
        "填空题来源字段：标准作业卡名称、是否落实（或可抽取的明确单值）\\n\\n"
        f"【输入内容 batch {batch_idx + 1}/{total_batches}】\\n{batch_text}\\n\\n"
        f"文件名：{filename}\\n"
    )
    if user_prompt:
        prompt += f"【用户补充要求】{user_prompt}\\n\\n"
    prompt += (
        "【输出格式示例】\\n"
        f"题目：该事故案例中可能出现哪些伤害后果？\\n"
        "题型：问答题\\n"
        "答案：\\n"
        "设备误启动造成机械卷入伤害；\\n"
        "化学品飞溅造成灼伤或中毒。\\n"
        "难度因子：0.5\\n"
        "来源字段：事故案例收集\\n\\n"
        f"题目：该标准作业卡的完整名称是______。\\n"
        "题型：填空题\\n"
        "答案：原料工区操作规程（配料岗位）\\n"
        "难度因子：0.2\\n"
        "来源字段：标准作业卡名称\\n"
        "请严格按照此格式输出，每题之间空一行，仅输出题目块。\\n"
    )
    return prompt

def get_risk_supplement_prompt(filename: str, row_text: str, existing_questions_count: int, existing_questions_text: str, need_questions: int, user_prompt: str = "", TOTAL_ROUNDS: int = 50) -> str:
    """获取风险识别补充问答生成提示词"""
    need_pairs = max(1, (need_questions + 1) // 2) # simplified math.ceil
    prompt = (
        f"你是一位风险识别补充问答生成专家。当前已有 {existing_questions_count} 道题，目标不少于 {TOTAL_ROUNDS} 道。"
        f"需再生成至少 {need_questions} 道题（约 {need_pairs} 组，1问答+1填空为一组），请利用下列内容深挖未覆盖要点。\\n\\n"
        "【补充生成要求】\\n"
        f"1. 目标生成 ≥{need_pairs} 组，严格问答题→填空题交替；若素材不足则输出最大可配对组数。\\n"
        "2. 问答题深挖：事故原因、风险诱因、控制措施逻辑、措施失效后果、落实状态差异。\\n"
        "3. 填空题聚焦：标准作业卡名称关键短语、是否落实的明确状态用语、控制措施中可抽取的核心短词或数值。\\n"
        "4. 禁止与已有题目文字重复或仅同义改写。\\n"
        f"5. 已有题目数: {existing_questions_count}，请避免重复。\\n"
        "6. 每题包含：题目、题型、答案、难度因子、来源字段；不得输出解释或总结。\\n"
        "7. 填空题仅一个空（______），答案必须出自原文。\\n"
        "8. 若无法生成至少1组则输出为空。\\n\\n"
        "【已有题目（避免重复）】\\n" + existing_questions_text + "\\n\\n" +
        "【原始内容】\\n" + row_text + "\\n"
    )
    if user_prompt:
        prompt += f"【用户补充要求】{user_prompt}\\n"
    return prompt


# ==================== SOP 问答生成提示词 ====================

def get_sop_qa_prompt(row_content: str, filename: str, extra_info: str, lang: str = "zh", user_prompt: str = "", min_pairs: int = 1, total_rows: int = 1, TOTAL_ROUNDS: int = 50) -> str:
    """
    SOP文件多字段问答对生成 Prompt（题型和难度自适应，题量随内容丰富度自动调整）
    lang: "zh" 为中文, "th" 为泰文, "en" 为英文
    """
    name = filename.split("/")[-1].rsplit(".", 1)[0]
    if lang == "th":
        instruction = (
            "คุณเป็นผู้เชี่ยวชาญในการสร้างคู่คำถาม-คำตอบ SOP โปรดปฏิบัติตามข้อกำหนดต่อไปนี้อย่างเคร่งครัด:\\n\\n"
            "【เป้าหมายการสร้างโดยรวม】\\n"
            f"ระบบคาดหวังว่าไฟล์ทั้งหมดจะมีคำถามไม่น้อยกว่า {TOTAL_ROUNDS} ข้อ ปัจจุบันมีข้อมูล {total_rows} แถว โปรดสร้างคำถามสำหรับแถวนี้ให้เพียงพอ\\n\\n"
            "【ข้อกำหนดขั้นต่ำสำหรับแถวนี้】\\n"
            f"แถวนี้ต้องสร้างอย่างน้อย {min_pairs} ชุด (1 ชุด = คำถามอัตนัย + คำถามเติมคำในช่องว่าง) รวมเป็น 2×{min_pairs} ข้อ "
            "โดยต้องสลับประเภท คำถามอัตนัย → คำถามเติมคำ อย่างเคร่งครัด หากเนื้อหาไม่เพียงพอให้คำนวณจำนวนชุดสูงสุด K ที่ทำได้ "
            "หาก K=0 ไม่ต้องส่งออกคำถามใดๆ ห้ามมีประเภทคำถามติดกัน\\n\\n"
            "【หลักการสร้างคำถาม】\\n"
            "1. คำถามอัตนัย (问答题): ถามเกี่ยวกับวัตถุประสงค์ วิธีการใช้งาน ประเด็นสำคัญ เหตุผล หรือข้อควรระวัง\\n"
            "2. คำถามเติมคำ (填空题): บริบทต้องสัมพันธ์กัน อนุญาตให้มีช่องว่างเดียวเท่านั้น (______) โดยช่องว่างต้องเป็นจุดปฏิบัติการสำคัญ ค่ามาตรฐาน หรือข้อควรระวัง\\n"
            "3. ทุกข้อต้องประกอบด้วยฟิลด์ภาษาจีน (เพื่อให้ระบบประมวลผลได้): 题目, 题型, 答案, 难度因子, 来源字段\\n"
            "4. ระดับความยาก: ง่าย (0~0.3), ปานกลาง (0.4~0.6), ยาก (0.7~1.0)\\n"
            "5. คำตอบต้องมาจากต้นฉบับ ห้ามแต่งขึ้นเอง คำตอบเติมคำต้องเป็นคำที่ปรากฏในข้อความจริง\\n"
            "6. การส่งออก: ห้ามใส่หมายเลขข้อ ห้ามใส่ JSON หรือคำอธิบายเพิ่มเติมใดๆ\\n\\n"
        )
        input_label = "【เนื้อหาอินพุต】"
        info_label = f"{extra_info}\\nชื่อไฟล์: {filename}"
        user_req_label = "【ข้อกำหนดเพิ่มเติมจากผู้ใช้】"
        example_label = "【ตัวอย่างรูปแบบการแสดงผล】"
        example_content = (
            f"题目：ก่อนเริ่มงาน ผู้ปฏิบัติงานต้องเตรียมตัวอย่างไร？\\n"
            "题型：问答题\\n"
            "答案：\\n"
            "ตรวจสอบสถานะอุปกรณ์และยืนยันมาตรการความปลอดภัย；\\n"
            "เตรียมเครื่องมือและวัสดุที่จำเป็น\\n"
            "难度因子：0.4\\n"
            "来源字段：รายละเอียดการปฏิบัติ (แยกย่อยท่าทาง)\\n\\n"
            f"题目：ระหว่างการปฏิบัติงานต้องสวม______ตลอดเวลา\\n"
            "题型：填空题\\n"
            "答案：ถุงมือป้องกัน\\n"
            "难度因子：0.2\\n"
            "来源字段：ความเสี่ยงพิเศษ\\n"
        )
        footer = "โปรดส่งออกตามรูปแบบนี้อย่างเคร่งครัด โดยเว้นวรรคหนึ่งบรรทัดระหว่างข้อ อย่าแสดงข้อความอื่นใด"
    elif lang == "en":
        instruction = (
            "You are a professional SOP QA pair generation expert. Please strictly follow the specifications below:\\n\\n"
            "【Overall Generation Goal】\\n"
            f"The system expects the entire document to have no less than {TOTAL_ROUNDS} questions (counting single questions). There are currently {total_rows} valid data rows, please contribute sufficient questions for this row.\\n\\n"
            "【Minimum Question Requirement for This Row】\\n"
            f"This row needs to generate at least M sets of questions (M={min_pairs}), each set containing 1 open-ended question + 1 fill-in-the-blank question, totaling 2×M questions, strictly alternating between open-ended and fill-in-the-blank questions.\\n\\n"
            "【Question Generation Principles】\\n"
            "1. Open-ended questions: Combine stages, steps, and work points to ask from angles such as 'What is the purpose?', 'How to operate?', 'What are the key points?', etc.\\n"
            "2. Fill-in-the-blank questions: The question stem must be contextually relevant, allowing only one blank (______).\\n"
            "3. Each question must include: question, question type, answer, difficulty factor, source field.\\n"
            "4. Difficulty factor: Easy (0~0.3), Medium (0.4~0.6), Hard (0.7~1.0).\\n"
            "5. Answers must come from the original text, fabrication is prohibited.\\n\\n"
        )
        input_label = "【Input Content】"
        info_label = f"{extra_info}\\nFilename: {filename}"
        user_req_label = "【Additional User Requirements】"
        example_label = "【Output Format Example】"
        example_content = (
            f"题目：Before starting the work, what preparations should the operator make?\\n"
            "题型：问答题\\n"
            "答案：\\n"
            "Check equipment status and confirm safety measures are in place;\\n"
            "Prepare necessary tools and materials.\\n"
            "难度因子：0.4\\n"
            "来源字段：Work Item Tasks\\n\\n"
            f"题目：During the operation, operators must wear ______.\\n"
            "题型：填空题\\n"
            "答案：protective gloves, safety helmet\\n"
            "难度因子：0.2\\n"
            "来源字段：Work Item Tasks\\n"
        )
        footer = "Please strictly follow this format for output, leaving one line space between questions. Do not output any additional explanations beyond this example."
    else:
        instruction = (
            "你是一位专业的SOP问答对生成专家，请严格遵守以下规范：\\n\\n"
            "【总体生成目标】\\n"
            f"系统期望整份文件最终不少于 {TOTAL_ROUNDS} 道题（单题计数）。当前共有 {total_rows} 行有效数据，请为本行充分贡献题量。\\n\\n"
            "【本行最低题量要求】\\n"
            f"本行需至少生成 M 组题目（M={min_pairs}），一组包含 1 道问答题 + 1 道填空题，共 2×M 道题，严格按 问答题→填空题 交替输出。\\n\\n"
            "【问答生成原则】\\n"
            "1. 问答题：结合阶段、步骤、作业点，可从‘目的是什么’‘应如何操作’‘包含哪些要点’等角度提问。\\n"
            "2. 填空题：题干需结合上下文，仅允许一个空（______）。\\n"
            "3. 每题必须包含：题目、题型、答案、难度因子、来源字段。\\n"
            "4. 难度因子：简单(0~0.3)、中等(0.4~0.6)、困难(0.7~1.0)。\\n"
            "5. 答案必须来自原文，禁止编造。\\n\\n"
        )
        input_label = "【输入内容】"
        info_label = f"{extra_info}\\n文件名：{filename}"
        user_req_label = "【用户补充要求】"
        example_label = "【输出格式示例】"
        example_content = (
            f"题目：在作业前，操作人员应完成哪些准备工作？\\n"
            "题型：问答题\\n"
            "答案：\\n"
            "检查设备状态，确认安全防护措施到位；\\n"
            "准备所需工具和材料。\\n"
            "难度因子：0.4\\n"
            "来源字段：作业事项任务\\n\\n"
            f"题目：操作过程中必须穿戴______。\\n"
            "题型：填空题\\n"
            "答案：防护手套、安全帽\\n"
            "难度因子：0.2\\n"
            "来源字段：作业事项任务\\n"
        )
        footer = "请严格按照此格式输出，每题之间空一行。不要输出本段示例以外的任何额外说明。"

    prompt = instruction
    prompt += f"{input_label}\\n{row_content}\\n\\n{info_label}\\n\\n"

    if user_prompt:
        prompt += f"{user_req_label}{user_prompt}\\n\\n"

    prompt += f"{example_label}\\n{example_content}\\n{footer}"
    return prompt

def get_sop_background_prompt(filename: str, row_content: str, lang: str = "zh") -> str:
    """获取 SOP 背景描述生成提示词"""
    if lang == "th":
        return (
            f"คุณเป็นผู้เชี่ยวชาญมืออาชีพในการวิเคราะห์เอกสารระเบียบปฏิบัติงาน (SOP) "
            f"โปรดสรุปข้อมูลบริบท (Background) ที่สั้นและกระชับจากเนื้อหาในแถวของ 《{filename}》 "
            f"เพื่อใช้เป็นข้อมูลพื้นฐานสำหรับการสร้างคู่คำถาม-คำตอบในลำดับต่อไป\\n\\n"
            "ข้อกำหนด:\\n"
            "1. แสดงเฉพาะข้อความสรุปบริบทเท่านั้น ไม่ต้องมีคำอธิบายเพิ่มเติมหรือหมายเหตุอื่นใด\\n"
            "2. ห้ามทำรายละเอียดสำคัญตกหล่น และให้มีความละเอียดครอบคลุมเนื้อหาที่ให้มามากที่สุด\\n"
            "3. ความยาวประมาณ 200-300 ตัวอักษรภาษาไทย (เพื่อให้ได้ใจความสมบูรณ์)\\n"
            "4. เขียนในรูปแบบย่อหน้าที่ต่อเนื่องกันเพียงย่อหน้าเดียว ห้ามใช้รายการสัญลักษณ์หรือหัวข้อย่อย (Bullet points)\\n"
            f"\\n【เนื้อหาแถวระเบียบปฏิบัติงาน】:\\n{row_content}\\n"
        )
    elif lang == "en":
        return (
            f"You are a professional SOP document analysis expert. Please extract a concise background introduction from the following row of 《{filename}》 to facilitate subsequent QA creation.\\n"
            "Requirements:\\n"
            "1. Output ONLY the background description text, without any additional explanations or notes.\\n"
            "2. Do not lose details; be as comprehensive as possible.\\n"
            "3. Length should be around 80-120 words.\\n"
            "4. Use a continuous paragraph format; do not use lists or bullets.\\n"
            f"\\n【SOP Row Content】:\\n{row_content}\\n"
        )
    else:
        return (
            f"你是一位专业的操作规程文档分析专家。请根据以下《{filename}》的行内容，提炼出一段简明扼要的背景介绍，便于后续问答对补充背景信息。\\n"
            "要求：\\n"
            "1. 仅输出背景描述文本，不要包含任何额外说明或注释\\n"
            "2. 不要丢失内容细节，尽可能详细\\n"
            "3. 字数在100字左右\\n"
            "4. 用连贯的段落形式表达，不要使用列表或分项\\n"
            f"\\n【操作规程行内容】:\\n{row_content}\\n"
        )

def get_sop_supplement_prompt(filename: str, row_content: str, existing_titles_count: int, need: int, extra_info: str, user_prompt: str = "", lang: str = "zh", TOTAL_ROUNDS: int = 50) -> str:
    """获取 SOP 补充问答生成提示词"""
    if lang == "th":
        prompt = (
            "คุณเป็นผู้เชี่ยวชาญในการสร้างคำถามเพิ่มเติมสำหรับ SOP\\n"
            f"ปัจจุบันมีคำถามบางส่วนแล้ว ยังคงต้องเพิ่มอีกประมาณ {need} ข้อ เพื่อให้ใกล้เคียงเป้าหมายรวม {TOTAL_ROUNDS} ข้อ\\n\\n"
            "ข้อกำหนด:\\n"
            "1. สร้างคำถามใหม่โดยต้องมีจำนวน 'คำถามอัตนัย' (问答题) และ 'คำถามเติมคำ' (填空题) เท่ากันและสลับประเภทกันอย่างเคร่งครัด\\n"
            "2. ห้ามซ้ำกับคำถามเดิมที่มีอยู่แล้ว (ตรวจสอบจากรายการหัวข้อที่มีอยู่)\\n"
            "3. คำตอบต้องมาจากเนื้อหาต้นฉบับเท่านั้น หากเนื้อหาไม่เพียงพอสามารถสร้างจำนวนน้อยกว่าที่กำหนดได้\\n"
            "4. ทุกข้อต้องใช้รูปแบบฟิลด์ภาษาจีน (เพื่อให้ระบบประมวลผลได้): 题目, 题型, 答案, 难度因子, 来源字段\\n"
            "5. แสดงเฉพาะรายการคำถามเท่านั้น ห้ามมีคำอธิบายประกอบหรือสรุปใดๆ ทั้งสิ้น\\n\\n"
            f"จำนวนหัวข้อคำถามที่มีอยู่เดิม: {existing_titles_count} ข้อ (ไม่ต้องระบุรายการเดิมซ้ำ)\\n"
            f"เนื้อหาอินพุต: {row_content}\\n"
            f"{extra_info}\\n" 
            f"ชื่อไฟล์: {filename}\\n"
        )
        if user_prompt:
            prompt += f"ข้อกำหนดเพิ่มเติมจากผู้ใช้: {user_prompt}\\n"
    elif lang == "en":
        prompt = (
            "You are an expert in generating supplementary questions for SOP.\\n"
            f"There are already some questions, and about {need} more questions need to be added to approach the overall goal of {TOTAL_ROUNDS}.\\n"
            "Requirements: Generate new questions with strictly equal numbers of open-ended and fill-in-the-blank types, alternating; no duplication with existing questions; answers must still come from the original text. Fewer questions can be generated if material is insufficient.\\n"
            "Maintain the previous format for each question: question, question type, answer, difficulty factor, source field. Output only the question blocks. No explanations allowed.\\n"
            f"Existing question title set size: {existing_titles_count} (no need to list).\\n"
            f"Input content: {row_content}\\n"
            f"{extra_info}\\n" 
            f"Filename: {filename}\\n"
        )
        if user_prompt:
            prompt += f"User additional requirements: {user_prompt}\\n"
    else:
        prompt = (
            "你是一位SOP补充问答生成专家。\\n"
            f"当前已有部分题目，仍需增加约 {need} 道题以接近全局目标 {TOTAL_ROUNDS}。\\n"
            "要求：生成若干新题，保持问答题与填空题数量严格相等并交替；不得与已存在题目重复；答案仍必须来源于原文。素材不足可少生成。\\n"
            "每题保持之前格式：题目、题型、答案、难度因子、来源字段。只输出题目块。禁止说明。\\n"
            f"已有题目标题集合大小：{existing_titles_count}（不需列出）。\\n"
            f"输入内容：{row_content}\\n"
            f"{extra_info}\\n" 
            f"文件名：{filename}\\n"
        )
        if user_prompt:
            prompt += f"用户补充要求：{user_prompt}\\n"
    return prompt


# ==================== 考试知识点生成提示词 ====================

def get_knowledge_point_extraction_prompt(structured_row: str, min_pairs: int) -> str:
    """获取知识点提取提示词"""
    return f"""
        你是考试知识点规划助手。

        下面是一行Excel结构化数据，请从中挑选适合出题的“知识点”，并判断该知识点更适合出【问答题】还是【填空题】。

        【选择规则】
        1. 优先选择：
           - 操作动作（如：具体做什么）
           - 判定标准 / 结果要求（如：做到什么程度）
           - 数值、条件、规格
           - 风险与管控
           - 材料与工具
        2. 不要选择：
           - 行号、步骤序号，阶段内容本身
           - 图片ID或公式
           - 空值 "/" 或 无意义内容
        3. 每个知识点必须可以单独用于出一道题
        4. 至少输出 {min_pairs} 个知识点，不足则输出全部可用内容
        5. “可出题内容”必须完全摘自原字段，不得改写

        【题型判定规则】
        - 如果内容是多个步骤、多个要点、操作流程、判定标准 → 题型 = "问答题"
        - 如果内容是单个名词、物品名称、部件、数值、唯一术语 → 题型 = "填空题"

        【输入数据】
        {structured_row}

        【输出要求】
        - 只允许输出 JSON 数组
        - 不要输出解释说明
        - 不要输出多余文字
        - 字段名必须来自输入数据 key

        【JSON输出格式】
        [
          {{
            "字段": "字段名",
            "可出题内容": "字段中的原文片段",
            "题型": "问答题 或 填空题"
          }}
        ]
    """

def get_essay_question_prompt(step1_out: str, background_text: str) -> str:
    """获取问答题生成提示词"""
    return f"""
        你是考试出题专家，请基于下面的知识点生成【问答题】。

        【作业背景】
        {background_text}

        说明：
        - 背景用于提供场景信息，可引用角色、地点、设备或作业环境等。
        - 禁止直接把知识点内容拼入题干，也不要简单换句式复述知识点。

        【规则】
        1. 每个知识点生成1道问答题，仅生成经过有效性判断的知识点：
           - 知识点必须具有可展开说明的价值，例如包含操作步骤、判定标准、注意事项或多条要点。
           - 单一事实、单个数值、单一名词或只能复述为“如何……？”的知识点不生成题目。
        2. 题目必须自包含，不能出现“该行/本数据”等代词。
        3. 问答题应围绕以下方向设计：
           - **操作目的**：为什么需要做这一步？
           - **操作方法**：做这一步需要哪些具体步骤或方法？
           - **标准判定**：如何判断操作是否达到要求？
           - **注意要点**：操作中有哪些关键点或风险管控？
        4. 每道题必须结合字段中的具体对象（如作业点、任务名称、作业阶段），题干自然融入背景信息。
        5. 答案1~4条要点，必须完全来自知识点内容，不得扩展或引入外部信息。
        6. 不要生成填空题。

        【知识点列表】
        {step1_out}

        【输出要求】
        - 只允许输出 JSON 数组
        - 不要输出解释或多余文字
        - 每道题作为数组的一个元素
        - 答案字段为数组

        【JSON 输出格式】
        [
          {{
            "题目": "题干自然融入背景，避免直接复述知识点内容",
            "题型": "问答题",
            "答案": ["要点1","要点2"],
            "难度因子": 自行判断0~1,
            "来源字段": "知识点字段名称"
          }}
        ]

    """

def get_gap_filling_question_prompt(step1_out: str, background_text: str) -> str:
    """获取填空题生成提示词"""
    return f"""
        你是考试出题专家，请基于下面的知识点生成【填空题】。

        【作业背景】
        {background_text}

        所有题目必须基于以上背景场景展开，并且可以用背景去加强问题上下文，让题目更贴近真实作业环境，不要替换知识点

        【规则】
        1. 每个知识点生成1道填空题
        2. 题干只能有一个空 ______
        3. 答案必须是原文中的精确词语/短语/数值
        4. 题目必须自包含，不能出现“该行/本数据”等代词
        5. 不要生成问答题

        【知识点列表】
        {step1_out}

        【输出要求】
        - 只允许输出 JSON 数组
        - 不要输出解释或多余文字
        - 每道题作为数组的一个元素
        - 答案字段为字符串

        【JSON 输出格式】
        [
          {{
            "题目": "这里写融入背景之后的填空题题干，空格用 ______ 表示",
            "题型": "填空题",
            "答案": "原文答案",
            "难度因子": 自行根据题目判断难度因子大小，范围0～1,
            "来源字段":"知识点列表中所选出题知识点的字段名称"
          }}
        ]
    """

# ==================== 操作规程问答生成提示词 ====================

def get_operation_qa_prompt(row_content: str, filename: str, user_prompt: str = "", min_pairs: int = 1, total_rows: int = 1, lang: str = "zh", TOTAL_ROUNDS: int = 50) -> str:
    """
    操作规程文件问答对生成 Prompt（支持压缩 + 分批）
    增加：全局最小题量 TOTAL_ROUNDS 与本行最低组数 M (一组=问答+填空)。
    """
    # 提取文件名（不含扩展名）作为前缀
    name = filename.split("/")[-1].rsplit(".", 1)[0]

    if lang == "th":
        # --- 泰文指令逻辑 ---
        instruction = (
            "คุณเป็นผู้เชี่ยวชาญด้านความปลอดภัยและการวิเคราะห์ขั้นตอนการปฏิบัติงาน (SOP) โปรดปฏิบัติตามข้อกำหนดต่อไปนี้อย่างเคร่งครัด:\\n\\n"
            "【เป้าหมายการสร้างโดยรวม】\\n"
            f"เอกสาร 《{name}》 ทั้งหมดต้องมีคำถามไม่น้อยกว่า {TOTAL_ROUNDS} ข้อ ปัจจุบันมีข้อมูล {total_rows} แถว โปรดสร้างคำถามจากแถวนี้ให้ได้มากที่สุด\\n\\n"
            "【ข้อกำหนดขั้นต่ำสำหรับแถวนี้】\\n"
            f"ต้องสร้างอย่างน้อย {min_pairs} ชุด (1 ชุด = 1 ข้อถาม-ตอบ + 1 ข้อเติมคำ) รวมเป็น 2×{min_pairs} ข้อ "
            "โดยต้องสลับประเภทระหว่าง [ข้อถาม-ตอบ] และ [ข้อเติมคำ] อย่างเคร่งครัด หากเนื้อหาไม่พอให้ใช้จำนวนที่น้อยที่สุด K=min(ถามตอบ, เติมคำ) "
            "หาก K=0 ไม่ต้องแสดงผล ห้ามมีประเภทเดียวกันติดต่อกัน\\n\\n"
            "【กฎการสร้างคำถาม】\\n"
            "1. ข้อเติมคำ: อนุญาตให้มีช่องว่างเดียวเท่านั้น (______) และต้องเป็นคำสำคัญ\\n"
            "2. ทุกข้อต้องใช้ป้ายกำกับ (Labels) เป็นภาษาจีนเท่านั้น: 题目, 题型, 答案, 难度因子\\n"
            "3. ระดับความยาก: ง่าย (0~0.3), ปานกลาง (0.4~0.6), ยาก (0.7~1.0)\\n"
            "4. คำตอบต้องมาจากเนื้อหาต้นฉบับ ห้ามแต่งขึ้นเอง\\n"
            "5. การส่งออก: แสดงเฉพาะบล็อกคำถามเท่านั้น ห้ามมี JSON, ลำดับข้อ หรือคำอธิบายเพิ่มเติม\\n\\n"
        )
        input_label = "【เนื้อหาอินพุต】"
        info_label = f"ชื่อไฟล์: {filename}"
        user_req_label = "【ข้อกำหนดเพิ่มเติมจากผู้ใช้】"
        example_label = "【ตัวอย่างรูปแบบการแสดงผล (Label ต้องเป็นภาษาจีน)】"
        example_content = (
            f"题目：ก่อนเริ่มเดินเครื่องต้องตรวจสอบอะไรบ้าง？\\n"
            "题型：问答题\\n"
            "答案：\\n"
            "ตรวจสอบระบบหล่อลื่น；\\n"
            "เช็คตัวยึดให้แน่น\\n"
            "难度因子：0.5\\n\\n"
            f"题目：แรงดันขณะเครื่องทำงานปกติควรอยู่ที่ ______\\n"
            "题型：填空题\\n"
            "答案：0.4~0.6 MPa\\n"
            "难度因子：0.3\\n"
        )
        footer = "โปรดส่งออกตามรูปแบบนี้อย่างเคร่งครัด โดยเว้นวรรคหนึ่งบรรทัดระหว่างข้อ"

    elif lang == "en":
        # --- 英文指令逻辑 ---
        instruction = (
            "You are a professional safety production and SOP expert. Please strictly follow these requirements:\\n\\n"
            "【Overall Goal】\\n"
            f"The entire document 《{name}》 expects no less than {TOTAL_ROUNDS} questions. With {total_rows} rows available, please maximize the count for this row.\\n\\n"
            "【Min Requirement for This Row】\\n"
            f"Generate at least {min_pairs} pairs (1 Q&A + 1 Fill-in-the-blank), totaling 2×{min_pairs} questions. "
            "Strictly alternate between Q&A → Fill-in. If materials are insufficient, use K=min(Q&A, Fill-in). "
            "If K=0, output nothing. Never output the same type consecutively.\\n\\n"
            "【Rules】\\n"
            "1. Fill-in-the-blank: Exactly one blank (______) per question.\\n"
            "2. Labels MUST be in Chinese: 题目, 题型, 答案, 难度因子.\\n"
            "3. Difficulty: Easy (0~0.3), Medium (0.4~0.6), Hard (0.7~1.0).\\n"
            "4. Answers must be derived from the source text.\\n"
            "5. Output ONLY question blocks. No JSON, no numbering, no extra text.\\n\\n"
        )
        input_label = "【Input Content】"
        info_label = f"Filename: {filename}"
        user_req_label = "【User Requirements】"
        example_label = "【Output Example (Labels in Chinese)】"
        example_content = (
            f"题目：What checks are needed before starting the machine?\\n"
            "题型：问答题\\n"
            "答案：\\n"
            "Check lubrication system;\\n"
            "Inspect fasteners.\\n"
            "难度因子：0.5\\n\\n"
            f"题目：Normal operating pressure should be ______.\\n"
            "题型：填空题\\n"
            "答案：0.4~0.6 MPa\\n"
            "难度因子：0.3\\n"
        )
        footer = "Follow this format strictly. One blank line between questions."

    else:
        # --- 中文指令逻辑 ---
        instruction = (
            "你是一位专业的安全生产与标准作业问答生成专家，请严格遵守以下规范：\\n\\n"
            "【总体生成目标】\\n"
            f"整份《{name}》规程期望合计不少于 {TOTAL_ROUNDS} 道题。当前共有 {total_rows} 条记录，请为本条充分贡献题量。\\n\\n"
            "【本条最低题量要求】\\n"
            f"需至少生成 {min_pairs} 组题目（1组 = 1道问答 + 1道填空），共 2×{min_pairs} 题。严格按 问答题→填空题 交替输出。 "
            "若素材不足，则取可配对最大组数 K=min(问答, 填空)；若 K=0 则不输出。严禁同题型连续出现。\\n\\n"
            "【题型与规则】\\n"
            "1. 填空题：题干仅允许一个空（______）。\\n"
            "2. 必须包含字段：题目、题型、答案、难度因子。\\n"
            "3. 难度因子：简单(0~0.3)、中等(0.4~0.6)、困难(0.7~1.0)。\\n"
            "5. 答案源于原文。问答题列出1-4要点，填空题仅给出关键短语/数值。\\n"
            "6. 仅输出题目块，不要附加总结、统计、JSON、编号或‘示例’字样。\\n\\n"
        )
        input_label = "【输入内容】"
        info_label = f"文件名：{filename}"
        user_req_label = "【用户补充要求】"
        example_label = "【输出格式示例】"
        example_content = (
            f"题目：启动设备前应完成哪些检查？\\n"
            "题型：问答题\\n"
            "答案：\\n"
            "确认润滑系统正常；\\n"
            "检查紧固件无松动。\\n"
            "难度因子：0.5\\n\\n"
            f"题目：设备正常运行时压力应保持在______。\\n"
            "题型：填空题\\n"
            "答案：0.4~0.6 MPa\\n"
            "难度因子：0.3\\n"
        )
        footer = "请严格按照此格式输出，每题之间空一行，仅输出题目块。"

    # --- 组合最终 Prompt ---
    prompt = instruction
    prompt += f"{input_label}\\n{row_content}\\n\\n{info_label}\\n\\n"

    if user_prompt:
        prompt += f"{user_req_label}\\n{user_prompt}\\n\\n"

    prompt += f"{example_label}\\n{example_content}\\n{footer}"

    return prompt

def get_operation_supplement_prompt(filename: str, row_content: str, existing_titles_count: int, need: int, user_prompt: str = "", lang: str = "zh", TOTAL_ROUNDS: int = 50) -> str:
    """补充生成操作规程问答，平衡问答/填空并接近 TOTAL_ROUNDS"""
    name = filename.split("/")[-1].rsplit(".", 1)[0]
    if lang.lower() == "en":
        prompt = (
            "You are an expert in generating supplementary Q&A for procedure documents.\\n"
            f"The current number of questions is below the target of {TOTAL_ROUNDS}. This time, please add approximately {need} more questions.\\n"
            "Requirements: Maintain a strict balance and alternation between Q&A and Fill-in-the-blank questions; do not repeat any existing questions; all answers must be derived from the original text or its paraphrases. If materials are insufficient, generate fewer.\\n"
            "Do not output any explanations, statistics, or JSON outside of the question blocks. Each question should still include: 题目、题型、答案、难度因子\\n"
            f"Existing question count: {existing_titles_count} (no need to list).\\n"
            f"Input Content:\\n{row_content}\\n"
            f"Filename: {filename}\\n"
        )
        if user_prompt:
            prompt += f"User Additional Requirements: {user_prompt}\\n"
    elif lang.lower() == "th":
        prompt = (
            "คุณเป็นผู้เชี่ยวชาญด้านการสร้างคำถามและคำตอบเสริมสำหรับเอกสารขั้นตอนการปฏิบัติงาน\\n"
            f"จำนวนคำถามปัจจุบันต่ำกว่าเป้าหมายที่ตั้งไว้ที่ {TOTAL_ROUNDS} ครั้งนี้คาดหวังที่จะเพิ่มคำถามประมาณ {need} ข้อ\\n"
            "ข้อกำหนด: รักษาสมดุลและสลับกันอย่างเคร่งครัดระหว่างคำถาม-คำตอบและเติมคำในช่องว่าง; ห้ามทำซ้ำคำถามที่มีอยู่แล้ว; คำตอบทั้งหมดต้องมาจากข้อความต้นฉบับหรือการเขียนใหม่ในรูปแบบอื่น หากเนื้อหาไม่เพียงพอสามารถสร้างได้น้อยลง\\n"
            "ห้ามส่งออกคำอธิบาย สถิติ หรือ JSON นอกเหนือจากบล็อกคำถาม แต่ละคำถามยังคงต้องมี: 题目、题型、答案、难度因子。\\n"
            f"จำนวนคำถามที่มีอยู่: {existing_titles_count} (ไม่จำเป็นต้องแสดงรายการ)\\n"
            f"เนื้อหาอินพุต:\\n{row_content}\\n"
            f"ชื่อไฟล์: {filename}\\n"
        )
        if user_prompt:
            prompt += f"ข้อกำหนดเพิ่มเติมจากผู้ใช้: {user_prompt}\\n"
    else:  # 默认中文
        prompt = (
            "你是一位操作规程补充问答生成专家。\\n"
            f"当前已有部分题目，总题量仍低于目标 {TOTAL_ROUNDS}，本次期望新增约 {need} 题。\\n"
            "要求：新增题保持问答题与填空题数量严格相等并交替；题目不得与已存在题目重复；所有答案必须来源于原文或其同义改写。素材不足可少生成。\\n"
            "禁止输出除题目块外的任何说明、统计或JSON。每题依旧包含：题目、题型、答案、难度因子。\\n"
            f"已有题目数量：{existing_titles_count}（无需列出）。\\n"
            f"输入内容：\\n{row_content}\\n"
            f"文件名：{filename}\\n"
        )
        if user_prompt:
            prompt += f"用户补充要求：{user_prompt}\\n"
    return prompt


# ==================== 通用问答生成提示词 ====================

def get_excel_qa_prompt(row_content: str, filename: str, total_items: int, user_prompt: str = "", min_pairs: int = 1, lang: str = "zh", TOTAL_ROUNDS: int = 50) -> str:
    """
    根据excel行内容生成问答对.
    """
    name = filename.split("/")[-1].rsplit(".", 1)[0]
    if lang == "th":
        prompt = (
            f"คุณเป็นผู้เชี่ยวชาญด้านการสร้างชุดคำถาม-answer จากข้อมูล Excel โปรดสร้างชุดคำถาม-answer คุณภาพสูงจากแถวของไฟล์ 《{name}》 ให้ได้มากที่สุด\\n\\n"
            "【เป้าหมายโดยรวม】\\n"
            f"ทั้งไฟล์ต้องมีจำนวนข้ออย่างน้อย {TOTAL_ROUNDS} ข้อ ขณะนี้มีข้อมูลที่ใช้งานได้ {total_items} แถว แถวนี้ต้องสร้างอย่างน้อย M ชุด (M={min_pairs}) โดย 1 ชุด = คำถามแบบตอบสั้น 1 ข้อ + เติมคำ 1 ข้อ รวม 2×M ข้อ\\n"
            "หากข้อมูลไม่เพียงพอให้ใช้จำนวนชุดสูงสุดที่จัดได้จริง K; หาก K=0 ไม่ต้องส่งออกคำถาม\\n\\n"
            "【ข้อจำกัดที่ต้องเคร่งครัด】\\n"
            "1. การสลับรูปแบบ: ต้องเรียงลำดับแบบ คำถามตอบสั้น → เติมคำ → คำถามตอบสั้น → เติมคำ ... อย่างเคร่งครัด\\n"
            "2. ห้ามใช้สรรพนามกำกวม: เช่น \"แถวนี้\" \"คอลัมน์นี้\" \"ข้อมูลนี้\" ฯลฯ ข้อคำถามต้องอธิบายตนเองและชัดเจน\\n"
            "3. ห้ามออกข้อคำถามจากฟิลด์ที่ไม่ก่อให้เกิดประโยชน์ทางธุรกิจ เช่น \"ลำดับ\" \"หมายเลข ID\" (ยกเว้นเป็นดัชนีสำคัญ) หรือ \"หมายเหตุว่าง\"\\n\\n"
            "【รูปแบบคำตอบ】\\n"
            "- คำถามตอบสั้น: สรุปประเด็นสำคัญ 1~4 ประเด็น รายการละ 1 บรรทัด ต้องมาจากต้นฉบับ 100%\\n"
            "- เติมคำ: มีช่องว่าง ______ เพียงช่องเดียวในโจทย์ คำตอบต้องเป็นคำ/วลี/ตัวเลขที่ปรากฏในต้นฉบับอย่างแม่นยำ\\n"
            "- ปัจจัยความยาก: ง่าย(0~0.3) ปานกลาง(0.4~0.6) ยาก(0.7~1.0)\\n\\n"
            "【ลำดับความสำคัญในการออกข้อ】 ฟิลด์สำคัญ ค่าตัวเลข คำอธิบาย ความเสี่ยง ฯลฯ\\n"
            "【ห้ามออกข้อ】 แถวว่าง ฟิลด์ที่เป็นเพียงลำดับเลข\\n"
        )
        # 泰语示例内容
        question_example_1 = f"คำถาม：เมื่อเกิดอุบัติเหตุไหม้กรดในที่เกิดเหตุ ควรปฏิบัติการช่วยเหลือขั้นต้นอย่างไร?"
        answer_example_1 = "คำตอบ：\\n1. ถอดเสื้อผ้าที่ปนเปื้อนออกทันที\\n2. ล้างด้วยน้ำสะอาดไหลเวียนอย่างน้อย 15 นาที\\n3. รีบไปพบแพทย์"
        question_example_2 = f"คำถาม：ห้ามใช้ ______ ในการดับเพลิงเมื่ออุปกรณ์ไฟฟ้าในห้องปฏิบัติการเกิดไฟไหม้"
        answer_example_2 = "คำตอบ：น้ำ"
    elif lang == "en":
        prompt = (
            f"You are an expert in generating high-quality Q&A pairs from Excel data. Create as many quality Q&A pairs as possible based on the row content from file 《{name}》.\\n\\n"
            "【Overall Objective】\\n"
            f"The entire file should have at least {TOTAL_ROUNDS} questions. Currently there are {total_items} valid data rows, this row must generate at least M sets (M={min_pairs}), each set = 1 short-answer question + 1 fill-in-the-blank question, totaling 2×M questions.\\n"
            "If there's insufficient material to reach M sets, use the actual maximum number of possible sets K; if K=0, do not output any questions.\\n\\n"
            "【Strict Constraints】\\n"
            "1. Alternating Format: Must strictly follow the sequence Short-answer → Fill-in-the-blank → Short-answer → Fill-in-the-blank...\\n"
            "2. Avoid Ambiguous Pronouns: Do not use ambiguous terms like \"this row\", \"this column\", \"this data\", etc. Questions must be self-contained and clear.\\n"
            "   - Incorrect example: What is the temperature of this row?\\n"
            "   - Correct example: What was the operating temperature setting for 【Device A-01】 in 2023?\\n"
            "3. Prohibited Question Sources: Do not create questions from non-business-beneficial fields such as \"sequence\", \"ID number\" (unless it's a critical index), or \"empty remarks\".\\n\\n"
            "【Answer Format】\\n"
            "- Short-answer question: Summarize 1~4 key points, one point per line, must be 100% from original text\\n"
            "- Fill-in-the-blank: Contains only one blank ______ in the question, the answer must be exact words/phrases/numbers appearing in the original\\n"
            "- Difficulty factor: Easy(0~0.3) Medium(0.4~0.6) Hard(0.7~1.0)\\n\\n"
            "【Priority Topics】Important fields, numerical values, descriptions, risks, etc.\\n"
            "【Prohibited Topics】Empty rows, fields that contain only sequence numbers.\\n"
        )
        question_example_1 = f"Question：What is the primary first aid measure when acid burn accident occurs on site?"
        answer_example_1 = "Answer：\\n1. Immediately remove contaminated clothing\\n2. Rinse with plenty of running water for at least 15 minutes\\n3. Seek medical attention promptly"
        question_example_2 = f"Question：It is strictly prohibited to use ______ for fire extinguishing when electrical equipment in laboratory catches fire."
        answer_example_2 = "Answer：water"
    else:
        prompt = (
            f"你是专业的Excel数据问答生成专家。根据《{name}》的行内容尽可能生成多的高质量问答对。\\n\\n"
            "【总体目标】\\n"
            f"整份文件期望总题数不少于 {TOTAL_ROUNDS}。当前共有 {total_items} 行有效数据，本行需至少生成 M 组题（M={min_pairs}），每组=1问答题+1填空题，总计 2×M 题。\\n"
            "若素材不足无法达到 M 组，取实际可配对最大组数 K；K=0 则不输出任何题目。\\n\\n"
            "【严格约束】\\n"
            "1. **交替输出**：严格按照 问答题 → 填空题 → 问答题 → 填空题... 的顺序排列。\\n"
            "2. **拒绝代词**：题目中**严禁**出现“该行”、“这一列”、“本数据”、“第一个字段”等指代不明的词汇。题目必须自包含（Self-contained）。\\n"
            "   - 错误示例：该行的温度是多少？\\n"
            "   - 正确示例：【设备A-01】在2023年的运行温度设定值是多少？\\n"
            "3. **禁止出题对象**：不要对“序号”、“ID编号”（除非是关键索引）、“备注为空”等无实际业务意义的字段出题。\\n\\n"
            "【答案规范】\\n"
            "- 问答题答案：提炼1~4个关键要点，每行一个；内容必须 100% 来自原文。\\n"
            "- 填空题：题干一个空 ______，答案为原文出现的精确词语/短语/数值。\\n"
            "- 难度因子：简单(0~0.3)、中等(0.4~0.6)、困难(0.7~1.0)。\\n\\n"
            "【优先出题方向】关键字段、数值、描述、风险等。\\n"
            "【禁止出题】纯序号、无内容空行。\\n"
        )
        # 中文示例内容
        question_example_1 = f"题目：在发生酸性灼伤事故时，现场急救的首要措施是？"
        answer_example_1 = "答案：\\n1. 立即脱去被污染的衣物\\n2. 用大量流动清水冲洗至少15分钟\\n3. 及时就医"
        question_example_2 = f"题目：实验室内的电气设备起火时，严禁使用______进行灭火。"
        answer_example_2 = "答案：水"

    prompt += f"\\n【输入行内容】\\n{row_content}\\n\\n"
    if user_prompt:
        prompt += f"【补充要求】{user_prompt}\\n\\n"
    prompt += (
        "【输出格式示例】\\n"
        f"{question_example_1}\\n"
        "题型：问答题\\n"
        f"{answer_example_1}\\n"
        "难度因子：0.5\\n\\n"

        f"{question_example_2}\\n"
        "题型：填空题\\n"
        f"{answer_example_2}\\n"
        "难度因子：0.2\\n\\n"

        "【输出执行】\\n"
        "1.只输出题目块；每题之间空一行；\\n"
        "2.题目必须结合行内的主要标识符（如名称、型号）进行提问。\\n"
        "3.不输出任何说明。\\n"
    )
    return prompt

def get_universal_supplement_prompt(filename: str, content: str, existing_titles_count: int, need: int, user_prompt: str = "", TOTAL_ROUNDS: int = 50) -> str:
    """
    生成补充 QA.
    """
    name = filename.split("/")[-1].rsplit(".", 1)[0]
    prompt = (
        f"你是补充问答生成专家。当前已有部分题目，总题量低于 {TOTAL_ROUNDS}，期望新增约 {need} 题。\\n"
        "要求：\\n"
        "1. 必须严格按 问答题→填空题→问答题→填空题... 交替，问答题与填空题数量相等；素材不足可少生成。\\n"
        "2. 不得与已有题目重复（无需列出现有题目）。\\n"
        "3. 所有答案必须来自原文；填空题题干仅一个空 ______；问答题答案为1~4个关键要点分行给出。\\n"
        "4. 难度因子为 0~1 之间的小数。\\n"
        "\\n【输入内容】\\n"
        f"{content}\\n"
        f"\\n【文件名】{filename}\\n"
    )
    if user_prompt:
        prompt += f"用户补充要求：{user_prompt}\\n"
        # 统一输出格式，确保 parse_qa_response 能解析
    prompt += (
        "【输出格式示例】\\n"
        f"题目：在发生酸性灼伤事故时，现场急救的首要措施是？\\n"
        "题型：问答题\\n"
        "答案：\\n"
        "1. 立即脱去被污染的衣物\\n"
        "2. 用大量流动清水冲洗至少15分钟\\n"
        "3. 及时就医\\n"
        "难度因子：0.5\\n\\n"

        f"题目：实验室内的电气设备起火时，严禁使用______进行灭火。\\n"
        "题型：填空题\\n"
        "答案：水\\n"
        "难度因子：0.2\\n\\n"
        "【输出要求】只输出题目块；每题之间空一行；不输出任何说明。\\n"
    )
    return prompt
