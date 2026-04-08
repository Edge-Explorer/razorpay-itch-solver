<div align="center">

# Razorpay Fix My Itch — AI Engineering Portfolio

**Production-grade AI solutions built for verified, real-world problems.**

[![Platform](https://img.shields.io/badge/Source-Razorpay%20Fix%20My%20Itch-3395FF?style=for-the-badge)](https://razorpay.com/m/fix-my-itch/)
[![Stack](https://img.shields.io/badge/Stack-Agents%20%7C%20FastAPI%20%7C%20Celery%20%7C%20Docker-7B2FBE?style=for-the-badge)](https://github.com/Edge-Explorer/razorpay-itch-solver)
[![Status](https://img.shields.io/badge/Status-Production%20Ready-2ECC71?style=for-the-badge)](https://github.com/Edge-Explorer/razorpay-itch-solver)

</div>

---

## Overview

This repository is a collection of independently deployable, production-grade AI systems — each one built to solve a specific problem sourced from [Razorpay's Fix My Itch](https://razorpay.com/m/fix-my-itch/), a platform that has catalogued over 10,000 verified pain points reported by more than 50,000 users across India.

Every project here was chosen intentionally. The problems are not hypothetical. They are real friction points reported by real users in the Indian financial and business ecosystem. The solutions are not prototypes — they are designed from the ground up for correctness, scalability, and production deployment.

---

## The Philosophy

The majority of developer portfolios demonstrate technical syntax, not engineering judgment. They show that the developer can write code, not that they can identify a problem worth solving and architect a system that solves it reliably.

This portfolio operates on a different principle: every project begins with a validated user problem, not a technology. The technology is chosen to fit the problem, not the other way around.

The result is a set of systems that reflect how software is built in a professional engineering environment — with deliberate architecture decisions, documented trade-offs, asynchronous design, and an emphasis on operational reliability.

> "A recruiter or engineering lead reading this repository should understand not just what was built, but why every technical decision was made."

---

## Engineering Process

Each problem goes through the following structured pipeline before a single line of code is written:

| Phase | Description |
|-------|-------------|
| Problem Qualification | Evaluate the problem's scope, user impact, and technical complexity using the Fix My Itch dataset |
| System Design | Define the architecture, data flow, infrastructure components, and AI approach |
| Technology Selection | Choose each library, framework, and service with a documented justification |
| Implementation | Build with production practices: async I/O, Pydantic validation, typed interfaces, and structured error handling |
| Hardening | Add audit trails, retry mechanisms, and fail-safe parsing to ensure the system degrades gracefully under failure |
| Documentation | Write a comprehensive README that explains every architectural and engineering decision |

---

## Portfolio

| # | Project | Problem Statement | Domain | Status |
|---|---------|-------------------|--------|--------|
| 1 | [Supplier Verification AI Engine](./problem-supplier-verification-ai-engine/README.md) | Businesses have no reliable, fast mechanism to verify new suppliers before entering a financial relationship, creating a critical window for fraud and impersonation. | B2B FinTech | Production-Ready |

---

## Core Technology Stack

The stack for each project is selected based on what the problem demands. The following technologies are used across this portfolio:

| Layer | Technology | Rationale |
|-------|-----------|-----------|
| AI Agent | Google Gemini 2.0 Flash with AFC | Fastest Gemini model; native tool-calling for autonomous research |
| Web Research | Tavily Search API | Structured, source-attributed search results; no scraping complexity |
| API Layer | FastAPI (async) | Non-blocking request handling; essential for high-concurrency workloads |
| Task Queue | Celery with Redis | Industry-standard distributed task processing; supports retry and late acknowledgment |
| Database | Neon PostgreSQL via asyncpg | Serverless Postgres with connection pooling; zero-idle cost |
| ORM | SQLAlchemy (async) | Mature async ORM with Alembic migration support |
| Containerization | Docker Compose | Single-command local orchestration of multi-service stacks |
| Scaling | Kubernetes with HPA | Horizontal pod autoscaling based on real-time CPU metrics |

---

## Contact

- **Problem Source**: [Razorpay Fix My Itch](https://razorpay.com/m/fix-my-itch/)
- **GitHub**: [Edge-Explorer](https://github.com/Edge-Explorer)

---

<div align="center">
<sub>Each problem in this repository was chosen deliberately. Each solution was built to hold up in production.</sub>
</div>
