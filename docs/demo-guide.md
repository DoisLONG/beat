# BEAT Demo Guide

This guide helps evaluators review the BEAT: OPEA-based Enterprise SOP Coaching and Assessment Agent.

## 1. Online Demo Environment

An online demo environment is available for challenge evaluation.

- Demo URL: https://14.103.144.187:30111/dashboard
- Demo account: user1-en
- Demo password: admin123

If the browser shows a certificate warning, please continue to the site for demo evaluation.

## 2. Local Deployment

The system can also be started locally with Docker Compose.

```bash
cd deployment/docker-compose
bash quickstart-dfxw.sh
```

After startup, open the local web UI:

```text
https://localhost:5174
```

If `EKBA_UI_PORT` is changed in `deployment/docker-compose/dfxw/.env`, use the configured port instead.

## 3. Demo Workflow

A typical evaluation workflow is:

1. Open the online demo environment or start the local Docker Compose deployment.
2. Log in with the demo account or the locally configured account.
3. Enter the learning, practice, or dashboard module.
4. Select or upload SOP / training materials.
5. Run knowledge preparation if needed.
6. Ask SOP-related questions through the Q&A interface.
7. Start an intelligent practice or exam session.
8. Submit answers as a learner.
9. Review the assessment result, explanation, and feedback.
10. Check learning records, wrong-answer review, or dashboard analytics.

## 4. What to Evaluate

The demo is designed to show the following capabilities:

- Enterprise SOP knowledge ingestion and preparation
- RAG-based Q&A grounded in training materials
- Intelligent practice and exam workflow
- LLM-assisted answer assessment
- Evidence-backed feedback and explanation
- Learning records and dashboard analytics
- OPEA-style modular GenAI architecture

## 5. Expected End-to-End Flow

```text
SOP / Training Material
    -> Knowledge Preparation
    -> Vector Retrieval
    -> RAG-based Q&A
    -> Intelligent Practice
    -> Answer Assessment
    -> Follow-up Feedback
    -> Learning Records and Dashboard
```

## 6. Notes for Evaluators

The online demo environment is provided for challenge evaluation and functional review.

Please do not upload confidential customer data, private enterprise documents, production logs, or sensitive personal information during public evaluation.

For a deeper technical explanation, please refer to:

- `README.md`
- `technical-report.pdf`
- `technical-report.md`
- `docs/engine-overview.svg`
- `docs/cloud-native-architecture.svg`
