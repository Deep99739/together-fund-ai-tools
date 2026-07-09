# NovaSummarize AI — Technical Architecture Overview

## Product Description
NovaSummarize is an AI-powered document summarization platform for enterprise legal teams. We help law firms process contracts 10x faster using cutting-edge AI.

## Architecture

### Core Technology Stack
- **Frontend**: React.js web application
- **Backend**: Node.js Express API server
- **Database**: PostgreSQL for user data, document metadata
- **AI Engine**: OpenAI GPT-4o API for all summarization tasks

### How It Works
1. User uploads a PDF document through our web interface
2. Our backend extracts text using pdf-parse npm package
3. The extracted text is sent to OpenAI GPT-4o via API with our custom prompt template
4. GPT-4o returns the summary, which we display to the user
5. Users can ask follow-up questions about the document (also routed to GPT-4o)

### Our Custom Prompts
We've spent 6 months perfecting our prompt templates:
- Contract Summary Prompt (optimized for legal documents)
- Key Terms Extraction Prompt
- Risk Identification Prompt
- Compliance Check Prompt

### Deployment
- Hosted on Vercel (frontend) and Railway (backend)
- Single-server deployment
- No caching layer currently implemented

### Data Handling
- Documents are temporarily stored for processing, then deleted after 24 hours
- We don't retain any customer data for training
- All processing happens via OpenAI's API (data leaves our system)

### Pricing
- $99/month per user
- Pay-per-document pricing for enterprise ($2 per document processed)
- Our costs are approximately $0.15 per document in API calls

### Team
- 2 co-founders (both full-stack developers, no ML experience)
- 1 contract designer
- No dedicated ML/AI engineers

### Roadmap
- Add support for Anthropic Claude as backup model
- Implement batch processing for large document sets
- Build Chrome extension for in-browser summarization
- Explore fine-tuning GPT-4 on legal corpus (Q3 2026)

### Competitive Advantage
- "Our prompts are our moat" — CEO
- Superior UX compared to using ChatGPT directly
- Focused specifically on the legal vertical
