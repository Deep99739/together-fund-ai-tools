# Cortex Security — Technical Architecture Document

## Product Description
Cortex Security is an AI-native threat detection and response platform for enterprise SOCs (Security Operations Centers). We use custom-trained models on proprietary security telemetry data to detect novel attack patterns that signature-based systems miss.

## Core Architecture

### Multi-Model Inference Pipeline
Our detection pipeline uses a cascade of 4 specialized models, each purpose-built:

1. **TelemetryEncoder v3** (Custom Transformer, 340M params)
   - Trained from scratch on 2.8B network flow events from 40 enterprise deployments
   - Encodes raw network telemetry (packet headers, flow metadata, DNS queries) into dense representations
   - Uses a custom attention mechanism optimized for temporal sequences with irregular timestamps
   - Fine-tuned bi-monthly on new attack telemetry from our customer base

2. **AnomalyClassifier** (Custom GNN + LSTM hybrid)
   - Graph neural network that models network topology and detects structural anomalies
   - LSTM component tracks behavioral patterns over 30-day windows per entity
   - Trained on 500K labeled security incidents + 12M normal behavior samples
   - Achieves 94.3% precision and 91.7% recall on our internal benchmark (CortexBench-2025)

3. **ThreatAttributor** (Fine-tuned LLaMA-3 70B, quantized to 4-bit)
   - Takes anomaly context + telemetry embeddings and produces threat attribution
   - Fine-tuned on our proprietary dataset of 50K attributed security incidents
   - Runs on-premise on customer infrastructure (supports air-gapped deployments)
   - Uses RAG over MITRE ATT&CK framework + our proprietary threat intelligence database

4. **ResponseOrchestrator** (Agentic system with tool use)
   - Multi-agent architecture: Planner → Executor → Validator → Documenter
   - Planner generates response playbooks based on threat type and severity
   - Executor can autonomously isolate machines, block IPs, rotate credentials (with configurable autonomy levels)
   - Validator checks all proposed actions against customer-defined safety policies
   - Documenter generates incident reports for compliance (SOC2, HIPAA, PCI-DSS)

### Proprietary Data Pipeline
- **Collection**: Custom lightweight agents deployed on customer endpoints, collecting 200M events/day per enterprise deployment
- **Processing**: Apache Kafka → Custom Flink processors → Feature store (Redis + Pinecone)
- **Labeling**: Proprietary labeling pipeline combining:
  - Expert SOC analyst annotations (partnership with 5 MSSPs)
  - Active learning loop where model uncertainty triggers human review
  - Synthetic attack generation using our AttackSimulator framework
- **Data Flywheel**: Every customer deployment generates labeled data that improves all models (with customer consent and privacy-preserving federation)

### Infrastructure
- **On-premise option**: Kubernetes-based deployment, supports air-gapped environments
- **Cloud option**: Multi-region GCP deployment with sub-100ms inference latency
- **Custom inference engine**: Built on vLLM with custom batching optimized for security workloads
- **Feature store**: Real-time feature computation with 50ms p99 latency across 2000+ features

### Evaluation & Testing
- **CortexBench-2025**: Our internal benchmark suite with 15K real-world attack scenarios
- **Continuous evaluation**: Automated red team that runs 1000 simulated attacks weekly
- **A/B testing framework**: Every model update tested against production in shadow mode
- **Customer-specific evaluation**: Each deployment has custom evaluation metrics based on their threat landscape

### Team
- 35 engineers (12 ML, 8 security domain experts, 10 infra, 5 product)
- Chief Scientist: Former head of detection engineering at CrowdStrike
- 3 published papers on temporal anomaly detection (USENIX Security, CCS)

### Competitive Moat
- 2.8B proprietary telemetry events (growing 200M/day)
- Custom models that can't be replicated with prompt engineering
- On-premise deployment capability (critical for defense and financial sector)
- SOC analyst labeling partnerships that provide exclusive training data
- 18 months of production deployment experience across 40 enterprises
