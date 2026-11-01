# 🎟️ EventBudget Intelligence — Autonomous AI Event Planner & Deterministic Ledger

> **Hackathon Project Submission**  
> *Transforming natural language event dreams into mathematically verified, budget-balanced vendor plans with live Google Maps navigation, direct phone contacts, and instant PDF export.*

---

## ⚡ The Big Idea (1-Minute Pitch)

Planning an event—whether a **pastel baby shower in Kolkata**, a **traditional Griha Pravesh in Bangalore**, or a **2-day beach wedding in Goa**—is notoriously stressful. Planners juggle dozens of chaotic quotes, hidden GST charges, unknown supplier locations, and fragile spreadsheets.

**Generative AI chatbots alone fail at this:** they hallucinate prices, make math errors on totals, and cannot provide verified driving coordinates or direct phone numbers.

**EventBudget Intelligence solves this through Hybrid AI Architecture:**
1. **Conversational Agent (Gemini 2.5 Flash + Fallback)**: Chat naturally in plain English or Hinglish without filling rigid forms.
2. **MCP Tool Orchestration**: Transparent tool traces for market benchmarking, supplier search, and tax compliance.
3. **Deterministic Financial Ledger**: 100% mathematically verified math, 18% GST calculation, 10% contingency buffers, and cost-per-guest unit economics.
4. **Zero-Friction Real World Actionability**: Direct click-to-call phone numbers, Google Maps driving navigation, and professional print-ready PDF export.

---

## 🛠️ Complete Tech Stack, Tools, APIs & MCP Overview

Here is the exact breakdown of all technologies, API keys, and tools used by this project:

| Component | Technology / Tool | API Key Required? | Notes & Architecture |
| :--- | :--- | :---: | :--- |
| **Conversational Agent** | **Google Gemini 2.5 Flash** | **Optional** (`VITE_GEMINI_API_KEY`) | Seamlessly calls Gemini via REST API. If no key is provided, gracefully falls back to the high-speed autonomous deterministic engine. **100% fail-safe for live judge demos!** |
| **MCP Architecture** | **Model Context Protocol Traces** | **No** (Built-in) | Implements MCP tool protocols: `mcp_vendor_pricing`, `web_search_engine`, `budget_optimizer`, `task_planner`, and `tax_compliance`. |
| **Geographic Navigation** | **Google Maps Universal Intent API** | **No** ($0 Free) | Uses Google's official navigation standard: `https://www.google.com/maps/search/?api=1&query=...`. Launches Google Maps app on mobile or desktop without billing keys. |
| **Direct Communication** | **Native `tel:` and `mailto:` protocols** | **No** (Built-in) | Instant one-tap calling to supplier managers and pre-filled inquiry email drafts. |
| **Document Export** | **Native Print-to-PDF Engine** | **No** (Zero external deps) | Formats a comprehensive executive plan with cost breakdowns, vendor directories, and checklists into PDF using `@media print`. |
| **Frontend Framework** | **React 19 + TypeScript + Vite** | **No** | Sub-second HMR, type-safe data structures, and optimized production builds. |
| **Design System** | **Neo-Brutalism (Tailwind CSS v4)** | **No** | High-contrast black borders (2px), bold shadows (`4px 4px 0 #000`), playful pastel badges, and 4px/8px spatial rhythm. |

---

## 🏗️ System Architecture

```mermaid
flowchart TD
    User([User Prompt: "Baby shower for 60 pax in Kolkata for ₹1.2L"]) --> UI[Neo-Brutalist Chat Interface]
    
    subgraph AI Intelligence Layer
        UI --> Dispatcher{API Key Present?}
        Dispatcher -- Yes --> Gemini[Google Gemini 2.5 Flash REST API]
        Dispatcher -- No / Offline --> HeuristicEngine[Autonomous Deterministic Engine]
    end

    subgraph MCP Tool Execution Pipeline
        HeuristicEngine --> Tool1[tool: web_search_engine]
        HeuristicEngine --> Tool2[tool: mcp_vendor_pricing]
        HeuristicEngine --> Tool3[tool: budget_optimizer]
        HeuristicEngine --> Tool4[tool: tax_compliance 18% GST]
        Gemini -. Enriches Advice .-> HeuristicEngine
    end

    subgraph Deterministic Ledger & Output
        Tool3 --> Ledger[Live Financial Ledger & Scenario Breakdown]
        Ledger --> Metrics[Telemetry Bar: Budget, Committed, Balance, Paid]
        Ledger --> Vendors[Vendor Directory: Phone, Map URL, GST, Scope]
        Ledger --> Tasks[Milestone Timeline & Checklists]
        Ledger --> PDFExport[Export Print-Ready PDF]
    end
```

---

## 🚀 How to Run the Project Locally

### 1. Prerequisites
- **Node.js** (v18.0 or higher recommended)
- **npm** or **pnpm**

### 2. Clone and Install Dependencies
```bash
# Navigate to project folder
cd promptwares_c5_ag

# Install dependencies
npm install
```

### 3. (Optional) Configure Gemini API Key
The app runs **100% out-of-the-box with ZERO API keys needed**.  
If you want to enable live Gemini 2.5 Flash calls:
```bash
# Copy example environment file
cp .env.example .env

# Edit .env and paste your free Google AI Studio key:
# VITE_GEMINI_API_KEY=your_gemini_api_key_here
```

### 4. Start Development Server
```bash
npm run dev
```
Open **`http://localhost:5173/`** in your browser.

---

## 🎯 Live Demo Walkthrough for Hackathon Judges

To give an unforgettable 2-minute demo to judges, follow this flow:

1. **The Blank Canvas**:
   - Show the clean Neo-Brutalist split interface.
   - Point out that **no signup or API key setup is required** to test.

2. **Natural Conversational Sourcing**:
   - Type or click one of the quick starters:
     > *"Plan a 60-guest pastel theme baby shower in Kolkata with high-tea buffet and decor for ₹1.2L."*
   - Watch the agent think and display **transparent MCP tool traces** (`web_search_engine`, `mcp_vendor_pricing`, `budget_optimizer`).

3. **Show the Deterministic Ledger (Right Column)**:
   - Highlight the **Live Telemetry Bar**: Planned ₹1.2L, 10% contingency buffer reserved (₹12,000), 18% GST calculated.
   - Point to the **Direct Contact Action Buttons**:
     - Click **"Maps"** to demonstrate instant Google Maps driving directions.
     - Click **"Call"** to show one-tap mobile connectivity.

4. **Dynamic Adjustment**:
   - In chat, type:
     > *"Tighten budget to ₹90,000 and switch to pure veg menu"*
   - Watch the agent re-calibrate all line items dynamically while maintaining budget balance!

5. **Export PDF**:
   - Click the green **"Export PDF"** button in the header.
   - Show the clean print preview with professional branding, vendor table, and milestone checklist.

---

## 🏆 Key Differentiators (Why This Wins Hackathons)

1. **Zero Hallucination Guarantee**: Mathematical ledger calculations are deterministic—no AI arithmetic errors.
2. **Offline / Network Resilient**: Will NEVER fail a live demo due to API rate limits or spotty convention hall Wi-Fi.
3. **Full Real-World Utility**: Real addresses, real phone numbers, real Google Maps URLs, and ready-to-share PDF contracts.
4. **Unique Neo-Brutalist Visual Identity**: Distinctive, vibrant, high-accessibility UI that stands out against generic dark-mode dashboards.

---

## 📄 License
MIT License. Created for the Hackathon 2026.
