# BEAT: OPEA-based Enterprise SOP Coaching and Assessment Agent

BEAT is an enterprise AI coaching and assessment platform designed for SOP-driven workforce training. It transforms enterprise SOP documents, training materials, operational procedures, and multimedia knowledge into traceable knowledge bases, interactive Q&A, automated exam generation, answer assessment, and evidence-backed learning feedback.

This project is submitted to the **AI for Good Innovation Challenge on Generative AI Applications for Enterprise Scenarios Using OPEA**.

The goal of BEAT is to demonstrate how OPEA-style modular GenAI components can be used to build a practical enterprise application for frontline worker training, continuous learning, and operational knowledge transfer.

---

## 1. Why BEAT Matters

In many industries, young workers do not start their careers in universities or research labs. They start in factories, restaurants, warehouses, retail stores, service desks, and field operation sites.

For them, the education gap is not an abstract concept. It appears in very practical moments: when a new machine is deployed, when a new safety rule is released, when a complex SOP is updated, or when they are expected to perform a task after only a short training session.

Traditional enterprise training often depends on thick manuals, one-time classroom sessions, fragmented mentoring, and the availability of experienced workers. As a result, frontline workers may struggle to access knowledge at the moment they need it most.

BEAT is designed to address this gap.

By using AI, RAG, LLM services, vector retrieval, workflow orchestration, and evidence-backed assessment, BEAT transforms enterprise knowledge into interactive learning experiences. It helps frontline workers understand complex procedures, practice key steps, receive immediate feedback, and build confidence before performing real tasks.

BEAT is not only about making enterprise training more efficient. It is about giving frontline workers a fairer and more continuous path to learn, improve, and grow in their careers.

---

## 2. Problem Statement

Enterprise SOP training faces several common challenges:

- SOP documents are often long, fragmented, and difficult for frontline workers to understand.
- Training sessions are usually one-time events, while real work requires repeated practice and timely feedback.
- Enterprise knowledge is scattered across PDF files, manuals, videos, spreadsheets, and experienced employees.
- Traditional Q&A systems may generate answers without reliable evidence or source references.
- Assessment results are often not connected to learning materials, making it difficult to explain why an answer is correct or incorrect.
- New procedures, safety rules, and equipment updates are difficult to distribute and reinforce at scale.

These challenges create a knowledge access gap between enterprise experts and frontline workers.

---

## 3. Solution Overview

BEAT provides an AI-powered coaching and assessment workflow for enterprise SOP training.

The system supports the following workflow:

1. Ingest SOP documents, manuals, training materials, and operational content.
2. Parse, chunk, and structure the knowledge.
3. Build a vector-based knowledge base.
4. Provide RAG-based Q&A with traceable references.
5. Generate scenario-based training questions.
6. Assess user answers using LLM-based evaluation.
7. Provide evidence-backed feedback linked to the original SOP content.
8. Generate learning records and assessment summaries.

The prototype focuses on a manufacturing-style SOP training scenario, but the same architecture can be extended to education, healthcare, customer support, public service, and other enterprise domains.

---

## 4. Key Features

### SOP Knowledge Ingestion

BEAT processes enterprise SOP documents and training materials, including:

- SOP manuals
- Safety procedures
- Operational guidelines
- Training documents
- Video/audio-derived text
- Structured and semi-structured content

### RAG-based Enterprise Q&A

The system retrieves relevant knowledge from the vector database and generates answers grounded in source materials.

Key capabilities:

- Context-aware answers
- Evidence-backed responses
- Reduced hallucination risk
- Source traceability

### Automated Exam Generation

BEAT can generate training questions based on enterprise SOP content.

Supported question types may include:

- Single-choice questions
- Multiple-choice questions
- Short-answer questions
- Scenario-based operational questions

### Answer Assessment

The system evaluates user answers based on SOP knowledge, expected actions, and task context.

Assessment output may include:

- Score
- Correctness judgment
- Explanation
- Missing key points
- Suggested review content
- Source references

### Learning Feedback Loop

BEAT connects training, practice, assessment, and review into a closed loop.

A typical learning loop includes:

1. Learn from SOP content.
2. Practice with generated questions.
3. Submit answers.
4. Receive evidence-backed feedback.
5. Review weak points.
6. Continue improvement.

### Multimodal Extension

The architecture can be extended to handle video-based training materials through ASR and structured content extraction.

---

## 5. OPEA-based Architecture

BEAT follows an OPEA-compatible modular GenAI architecture. The system is designed around reusable components such as LLM services, RAG pipelines, vector databases, orchestration workflows, and guardrail-oriented controls.

### Component Mapping

| OPEA Component | BEAT Module / Capability | Description |
|---|---|---|
| Knowledge Ingestion | `dataprep`, `asr`, `excel` | Parses documents, audio/video transcripts, and structured training materials |
| Embedding & Indexing | RAG pipeline | Converts SOP content into searchable vector representations |
| Vector DB | Milvus | Stores and retrieves enterprise knowledge chunks |
| LLM Service | External or configurable LLM service | Generates answers, questions, explanations, and assessment feedback |
| RAG Pipeline | SOP Q&A workflow | Retrieves source knowledge before generation |
| Orchestration | `smart-practice`, learning workflow | Coordinates question generation, answering, scoring, feedback, and review |
| Guardrails | Evidence grounding, state control, source references | Reduces hallucination and improves answer reliability |
| Evaluation | Assessment and learning report | Evaluates answer quality, learning progress, and SOP understanding |

### High-level Workflow

```text
SOP / Training Materials / Video Transcripts
                ↓
        Knowledge Ingestion
                ↓
      Chunking and Structuring
                ↓
       Embedding + Vector DB
                ↓
          RAG Retrieval
                ↓
             LLM Service
                ↓
      Agent / Workflow Orchestration
                ↓
  Coaching / Exam / Assessment / Feedback
                ↓
     Evidence-backed Learning Report
