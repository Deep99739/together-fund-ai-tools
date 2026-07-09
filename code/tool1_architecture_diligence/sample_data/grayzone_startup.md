# FinSight Copilot — Technical Architecture Notes

## Product Description
FinSight Copilot helps mid-market CFO teams detect revenue leakage, explain forecast variance, and prepare board-ready commentary from ERP, CRM, billing, and support data. The product is sold as an AI finance analyst for companies that have outgrown spreadsheets but do not yet have a full FP&A data engineering team.

## Core Architecture

### Data Ingestion and Normalization
- Connectors for NetSuite, QuickBooks, Salesforce, HubSpot, Stripe, Chargebee, Zendesk, and Snowflake.
- We maintain a normalized financial event schema covering invoices, subscriptions, renewals, discounts, collections, support escalations, and pipeline changes.
- Customers can define custom mapping rules when their chart of accounts or CRM stages are non-standard.
- We currently process about 180M historical records across 34 customers, but only 21M records are available for model training because many customers opt out of cross-customer learning.

### Model Stack
1. **VarianceClassifier v2** — fine-tuned DeBERTa model
   - Classifies revenue variance explanations into 14 categories such as churn, expansion delay, collections timing, discounting, billing error, and pipeline slippage.
   - Fine-tuned on 62K analyst-labeled variance explanations collected from customer FP&A reviews.
   - Achieves 87.4% macro-F1 on our internal validation set, but performance drops to 71% when customers have highly customized revenue recognition rules.

2. **RevenueGraph Embedding Layer** — custom graph feature pipeline
   - Builds a company-specific graph connecting accounts, products, invoices, opportunities, support tickets, and renewal events.
   - Uses a GraphSAGE-style embedding job to surface unusual customer/account transitions.
   - The embeddings are proprietary to each customer and are not pooled across tenants.

3. **NarrativeGenerator** — hosted LLM orchestration
   - Uses GPT-4o and Claude as interchangeable generation providers for board-commentary drafts.
   - The LLM receives retrieved variance evidence, graph anomalies, and policy rules; it does not directly query the warehouse.
   - We use strict templates and citation requirements, but the final narrative generation is still dependent on third-party model APIs.

4. **ExplanationGuard** — rules + evaluator model
   - Checks whether every generated sentence is backed by a source row, metric, or retrieved analyst note.
   - Uses a small fine-tuned classifier to flag unsupported claims before the report is shown to users.
   - Unsupported claims are blocked about 9% of the time in production.

### Evaluation and Reliability
- We run monthly evaluation suites on 420 anonymized FP&A scenarios.
- Current benchmark: 84% accepted explanations, 11% analyst edits, 5% rejected outputs.
- We monitor hallucination rate, missing-citation rate, connector failure rate, and time-to-report.
- Customers can enable a “review required” mode where no AI-generated commentary is exported without analyst approval.

### Infrastructure
- Backend services run on AWS ECS with Postgres, Redis, and Snowflake external tables.
- Customer data is logically isolated per tenant; enterprise customers can use their own Snowflake account.
- We have not yet built on-prem or air-gapped deployment.
- Vector retrieval uses pgvector today; we plan to move larger customers to a dedicated vector service if query latency increases.

### Team
- 14 engineers: 3 ML engineers, 5 backend/data engineers, 3 frontend engineers, 2 finance-domain product specialists, 1 security engineer.
- Founding team includes a former Stripe data platform lead and an ex-Director of FP&A from a public SaaS company.

### Defensibility Claims
- Proprietary labeled FP&A explanation dataset from real analyst workflows.
- Customer-specific revenue graph features are hard to reproduce without deep financial system integrations.
- Evaluation harness is improving with every customer deployment.
- However, board-commentary generation depends on hosted LLM APIs, and competitors could use similar LLM orchestration if they have access to comparable data.

### Known Limitations
- We do not train foundation models from scratch.
- We rely on third-party LLMs for polished narrative generation.
- Edge cases around custom revenue recognition require analyst review.
- Our strongest moat is the finance data normalization layer and labeled explanation corpus, not model ownership.
