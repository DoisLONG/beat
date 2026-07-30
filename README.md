# BEAT: OPEA-aligned Enterprise SOP Coaching and Assessment Agent

> AI for Good Innovation Challenge on Generative AI Applications for Enterprise Scenarios Using OPEA  
> Team: BlueDot BEAT Team  
> Repository: https://github.com/DoisLONG/beat

BEAT is an enterprise intelligent coaching and assessment system for SOP-driven workforce training. It is designed for internal enterprise scenarios such as standard operating procedures, operation manuals, emergency drills, safety training, job onboarding, and role-based competency assessment.

The system uses large language models, retrieval-augmented generation, vector retrieval, microservice orchestration, and learning-state management to convert enterprise training materials into an interactive learning workflow. It supports knowledge preparation, SOP-based question answering, intelligent exam coaching, answer assessment, follow-up explanation, learning records, and management dashboards.

This repository is submitted to the **AI for Good Innovation Challenge on Generative AI Applications for Enterprise Scenarios Using OPEA**. For the challenge, BEAT is positioned as an **OPEA-aligned enterprise GenAI application** that demonstrates how modular AI components can be used to solve a practical enterprise training problem.

---

## 1. Background

Enterprise training is often limited by static documents, one-time classroom sessions, and fragmented mentoring.

In many frontline work scenarios, employees need to understand complex procedures before performing real tasks. These procedures may involve equipment operation, safety rules, emergency response, quality inspection, service processes, or internal compliance requirements.

However, enterprise knowledge is often scattered across SOP documents, PDF manuals, videos, spreadsheets, and the experience of senior workers. New employees may face several practical difficulties:

- SOP documents are long and difficult to understand.
- Training happens once, but real work requires repeated practice.
- Experienced mentors are not always available.
- Workers may not know which step they missed after answering incorrectly.
- Assessment results are often not connected back to the original training material.
- Enterprises need a scalable way to train and evaluate workers across different sites and roles.

BEAT is designed to turn static enterprise knowledge into a continuous, interactive, and evidence-backed learning process.

---

## 2. Project Goal

The goal of BEAT is to provide an AI-powered SOP coaching and assessment workflow for enterprise workforce training.

The system aims to:

- Transform enterprise SOPs and training materials into reusable knowledge assets.
- Provide RAG-based Q&A grounded in source materials.
- Generate training and exam questions from enterprise knowledge.
- Evaluate user answers and provide feedback.
- Support follow-up explanation and review.
- Keep learning records and session history.
- Help managers understand learning progress and training effectiveness.

BEAT focuses on the complete learning loop:

```text
Knowledge ingestion
    -> SOP understanding
    -> interactive coaching
    -> exam generation
    -> answer assessment
    -> feedback and review
    -> learning records and dashboard
```

---

## 3. AI for Good Relevance

BEAT is not only an enterprise productivity tool. It also addresses a broader knowledge-access problem for frontline workers.

Many workers begin their careers directly in factories, warehouses, restaurants, stores, service desks, or field operation sites. For them, access to knowledge is often practical and time-sensitive. They need to understand how to perform a task, how to avoid mistakes, and how to improve step by step.

BEAT provides an always-available digital coaching layer for these workers. When a worker cannot understand a long manual, the system can help explain the procedure. When a worker forgets a key step, the system can generate practice questions. When a worker answers incorrectly, the system can provide feedback and point back to the relevant SOP content.

This makes workplace knowledge more accessible, repeatable, and traceable. It helps frontline workers continue learning inside real work environments.

---

## 4. OPEA Alignment

OPEA, the Open Platform for Enterprise AI, promotes modular, composable, and production-oriented GenAI applications for enterprise scenarios.

BEAT follows the same architectural direction. The system is organized around modular services for data preparation, retrieval, generation, orchestration, assessment, learning, and management.

### 4.1 OPEA-style Component Mapping

| OPEA Concept | BEAT Capability | Description |
| --- | --- | --- |
| Knowledge ingestion | `dataprep`, `asr`, `excel` | Processes documents, transcripts, structured files, and training materials |
| RAG pipeline | SOP-based Q&A and knowledge retrieval | Retrieves relevant enterprise knowledge before LLM generation |
| Vector database | Milvus-based retrieval layer | Stores and retrieves vectorized enterprise knowledge |
| LLM service | Q&A, question generation, scoring, explanation | Generates answers, questions, feedback, and assessment results |
| Orchestration | `smart-practice` workflow | Coordinates coaching, exam flow, answer assessment, and follow-up |
| Guardrail-oriented design | Source grounding and learning-state control | Reduces hallucination and improves traceability |
| Evaluation | Answer assessment and learning reports | Measures answer quality and learning progress |

### 4.2 High-level Architecture

```text
Enterprise SOPs / Manuals / Training Materials / Videos
                         |
                         v
              Data Preparation Services
        document parsing / ASR / structured extraction
                         |
                         v
             Knowledge Processing and Indexing
            chunking / metadata / vectorization
                         |
                         v
                  Vector Retrieval Layer
                         |
                         v
                    RAG-based Q&A
                         |
                         v
                  LLM Service Layer
       answer generation / question generation / scoring
                         |
                         v
              Smart Practice Orchestration
       exam flow / follow-up coaching / state management
                         |
                         v
          Learning Service / History / Dashboard
```

---

## 5. Core Capabilities

### 5.1 Knowledge Preparation

BEAT prepares enterprise knowledge from SOP documents, operation manuals, safety materials, emergency drill documents, audio/video transcripts, and structured files.

The knowledge preparation layer is responsible for parsing, converting, structuring, and preparing materials for downstream retrieval and training workflows.

### 5.2 RAG-based SOP Q&A

BEAT uses retrieval-augmented generation to answer user questions based on enterprise materials.

The purpose is to make answers:

- More relevant to the enterprise context.
- Grounded in retrieved source knowledge.
- Easier to verify and trace.
- More suitable for SOP training and operational learning.

### 5.3 Intelligent Exam Coaching

The `smart-practice` service is the core coaching component. It supports question generation, user answer processing, scoring, follow-up explanation, and learning feedback.

This turns static SOP content into an interactive training process.

### 5.4 Answer Assessment

BEAT evaluates user answers based on the expected procedure, key knowledge points, and retrieved SOP context.

Assessment results may include:

- Correctness judgment.
- Score or assessment conclusion.
- Explanation of missing points.
- Suggested review direction.
- Reference to related SOP content.

### 5.5 Learning Records and Management

BEAT supports learning history, session management, and dashboard-style analysis. This helps both learners and administrators understand training progress and weak points.

---

## 6. System Modules

The current system contains the following major service modules:

| Module | Description |
| --- | --- |
| `dataprep` | Data preprocessing and knowledge preparation |
| `smart-practice` | Intelligent coaching, exam generation, answer assessment, and feedback |
| `learn` | Learning service and learning records |
| `system-common` | Common system management service |
| `asr` | Audio/video speech-to-text service |
| `excel` | Structured processing service for spreadsheet or extracted multimodal content |
| `dashboard` | Dashboard and analytics service |
| `account` | Account and user management |
| `chathistory` | Conversation history and session management |

The system may use the following infrastructure components:

- MySQL
- MongoDB
- Redis
- Milvus
- MinIO or object storage
- External or configurable LLM service
- Document parsing service
- ASR service

---

## 7. Deployment

### 7.1 Runtime Requirements

The challenge requires a single-node evaluation environment. BEAT is designed to run in a single-node Docker Compose environment for the submitted prototype.

Recommended environment:

- OS: Ubuntu 22.04
- CPU: 4 cores or above
- Memory: 8GB to 64GB RAM, depending on enabled services
- Disk: 200GB recommended for full local deployment
- GPU: Optional
- Docker
- Docker Compose

### 7.2 Start the System

The current recommended deployment entry is the Docker Compose quickstart script:

```bash
cd deployment/docker-compose
bash quickstart-dfxw.sh
```

The script starts the required infrastructure services and BEAT application services.

### 7.3 Stop the System

```bash
cd deployment/docker-compose
bash quickstart-dfxw.sh stop
```

### 7.4 Deployment Notes

Before running the system, make sure that required environment variables, model service endpoints, object storage settings, and database settings are correctly configured.

Do not commit real API keys, customer data, private service URLs, internal IP addresses, production credentials, or confidential SOP documents to this repository.

---

## 8. Demo Workflow

A typical evaluator workflow is:

1. Start the system with the Docker Compose quickstart script.
2. Log in to the web interface.
3. Import or select an enterprise SOP/training material.
4. Ask SOP-related questions.
5. Review the generated answers and related knowledge context.
6. Start an intelligent practice or exam session.
7. Submit answers as a learner.
8. Review the assessment result and explanation.
9. Check learning records or dashboard information.

The expected demonstration flow is:

```text
SOP material
    -> knowledge preparation
    -> RAG-based Q&A
    -> exam generation
    -> answer assessment
    -> feedback and learning record
```

---

## 9. Evaluation Focus

This project is aligned with the AI for Good OPEA challenge evaluation criteria.

### 9.1 Creativity and Business Value

BEAT addresses a real enterprise training problem. It helps enterprises convert static SOP documents into interactive learning and assessment workflows.

Business value includes:

- Faster onboarding.
- Lower training cost.
- Better safety compliance.
- Reusable enterprise knowledge.
- Traceable assessment results.
- Scalable training across teams and sites.

### 9.2 Technical Implementation

BEAT demonstrates an OPEA-aligned modular GenAI architecture:

- Knowledge ingestion.
- RAG-based retrieval.
- Vector database support.
- LLM-based generation and assessment.
- Workflow orchestration.
- Guardrail-oriented source grounding.
- Learning records and dashboard analysis.

### 9.3 Prototype Quality

The prototype demonstrates a complete workflow from enterprise knowledge preparation to training, assessment, and feedback.

---

## 10. Data and Privacy

This repository should only contain code, configuration templates, and data that are suitable for public or challenge evaluation.

The submitted version should not include:

- Real customer SOP documents.
- Customer confidential information.
- Personal sensitive information.
- Internal IP addresses.
- Private service URLs.
- API keys or tokens.
- Production credentials.
- Private logs.

Any demo data used for the challenge should be public, synthetic, or properly authorized.

---

## 11. Open-source License

This project is licensed under the Apache License 2.0.

See the `LICENSE` file for details.

All third-party dependencies used in the submitted solution should be compatible with Apache 2.0 or MIT-style open-source licensing requirements.

---

## 12. Challenge Submission Information

- **Challenge:** AI for Good Innovation Challenge on Generative AI Applications for Enterprise Scenarios Using OPEA
- **Team:** BlueDot BEAT Team
- **Project name:** BEAT: OPEA-aligned Enterprise SOP Coaching and Assessment Agent
- **Project URL:** https://github.com/DoisLONG/beat
- **Target scenario:** Enterprise SOP training and assessment
- **Primary vertical:** Manufacturing / enterprise workforce training
- **OPEA-related components:** LLM, RAG, vector database, orchestration, guardrail-oriented design

---

## 13. Contact

For questions about this project, please use the GitHub repository issue or contact the project maintainer.



## Online Demo Environment

An online demo environment is available for challenge evaluation:

- Demo URL: `https://14.103.144.187:30111/dashboard`
- Demo account: `user1-en`
- Demo password: `admin123`

This demo environment is provided for evaluation and functional review. It is a test environment with limited access permissions.

If a browser shows a certificate warning, please continue to the site for demo evaluation.

