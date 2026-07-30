# BEAT Technical Report

**Challenge:** AI for Good Innovation Challenge on Generative AI Applications for Enterprise Scenarios Using OPEA  
**Team:** BlueDot BEAT Team  
**Project:** BEAT: OPEA-based Enterprise SOP Coaching and Assessment Agent

## Summary

BEAT transforms enterprise SOP documents, training manuals, videos, audio transcripts, and structured files into a closed-loop training workflow: knowledge preparation, RAG-based Q&A, intelligent practice, answer assessment, evidence-backed feedback, and learning analytics.

## Problem

Enterprise SOP training relies on static manuals, fragmented mentoring, and manual course creation. SOP updates are hard to distribute quickly, generic Q&A lacks traceability, and scoring or follow-up coaching is difficult to control.

## Solution

BEAT converts enterprise materials into traceable knowledge points, Q&A pairs, and practice questions. It uses RAG and vector retrieval to ground answers, scoring, and explanations in source content, building a learning-practice-assessment-feedback loop for SOP-driven workforce training.

## OPEA Component Mapping

- Knowledge ingestion: dataprep, ASR, Excel processing, document parsing.
- RAG layer: embeddings, Milvus vector database, retriever, rerank, and source-grounded context.
- LLM service: Q&A, question generation, answer evaluation, scoring, and explanation.
- Orchestration and guardrails: smart_practice workflow, session state, timer, answer logs, and traceability.
- Analytics: learn, chathistory, dashboard, account, and system_common.

## Deployment and Demo

- Single-node Docker Compose deployment: `deployment/docker-compose/quickstart-dfxw.sh`
- Local UI default: `https://localhost:5174`
- Online evaluation demo: `https://14.103.144.187:30111/dashboard`
- Demo account: `user1-en / admin123`

## Evaluation Focus

BEAT demonstrates creativity and business value through procedure-anchored frontline training, technical implementation through modular OPEA-style services, prototype quality through an end-to-end workflow, and compliance through Apache-2.0 licensing and sanitized public materials.
