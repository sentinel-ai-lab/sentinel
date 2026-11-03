import React, { useState, useEffect } from 'react';
import { 
  ShieldCheck, 
  AlertTriangle, 
  AlertOctagon, 
  HelpCircle, 
  CheckCircle2, 
  Sparkles, 
  FileText, 
  Send, 
  RotateCcw, 
  Copy, 
  Check, 
  ExternalLink, 
  Cpu, 
  Activity,
  Layers,
  ArrowRight
} from 'lucide-react';

const PRESET_CLAIMS = [
  {
    category: 'Advice Violation',
    claim: 'Investors should buy HDFC Bank shares immediately with a target price of ₹2,100 for guaranteed 25% returns.',
    badgeClass: 'banner-ADVICE_VIOLATION'
  },
  {
    category: 'Compliant Report',
    claim: 'Tata Consultancy Services reported consolidated revenue of ₹255,324 crore in FY2025, representing solid operational execution.',
    badgeClass: 'banner-COMPLIANT'
  },
  {
    category: 'Needs Disclaimer',
    claim: 'Infosys management expects operating margins to expand to 22.5% in FY2026 driven by Project Maximus automation.',
    badgeClass: 'banner-NEEDS_DISCLAIMER'
  },
  {
    category: 'Unsupported Claim',
    claim: 'State Bank of India will acquire a major German retail bank next quarter to expand European retail deposits.',
    badgeClass: 'banner-UNSUPPORTED'
  }
];

const PRESET_DRAFT = `Tata Consultancy Services achieved steady operating performance with revenue reaching ₹255,324 crore.
Investors must buy TCS shares immediately as it will deliver 30% rally by Diwali.
Management projects digital transformation demand will accelerate operating margins to 28% over the next fiscal year.
Furthermore, TCS is preparing to launch a private domestic airline carrier in India next month.`;

export default function App() {
  const [activeTab, setActiveTab] = useState('claim'); // 'claim' | 'draft' | 'copilot' | 'benchmarks'
  const [modelInfo, setModelInfo] = useState(null);
  const [loading, setLoading] = useState(false);
  const [copied, setCopied] = useState(false);

  // Tab 1: Single Claim State
  const [claimInput, setClaimInput] = useState(PRESET_CLAIMS[0].claim);
  const [claimResult, setClaimResult] = useState(null);

  // Tab 2: Draft Review State
  const [draftInput, setDraftInput] = useState(PRESET_DRAFT);
  const [reviewResult, setReviewResult] = useState(null);

  // Tab 3: Copilot State
  const [copilotInput, setCopilotInput] = useState('What was the total revenue and net profit of TCS in FY2025?');
  const [messages, setMessages] = useState([
    {
      role: 'assistant',
      text: 'Hello! I am Sentinel, an AI equity research assistant for Indian markets. Ask me any question on BSE/NSE filings or evaluate financial claims for SEBI compliance.',
      citations: []
    }
  ]);

  // Fetch model metadata
  useEffect(() => {
    fetch('/api/info')
      .then(res => res.json())
      .then(data => setModelInfo(data))
      .catch(() => {
        // Fallback info if API is starting up
        setModelInfo({
          model_id: 'kishanaik5/sentinel-compliance-qwen25-7b-lora',
          metrics: { macro_f1: 0.9963, accuracy: 0.9963, latency_p50_ms: 240, cost_per_query_usd: 0.0003 }
        });
      });
  }, []);

  const handleClassifyClaim = async () => {
    if (!claimInput.trim()) return;
    setLoading(true);
    setClaimResult(null);
    try {
      const res = await fetch('/api/compliance/classify', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ claim: claimInput })
      });
      const data = await res.json();
      setClaimResult(data);
    } catch (err) {
      setClaimResult({
        label: 'ERROR',
        explanation: 'Failed to connect to Sentinel API. Please ensure the backend is running.',
        rewrite: claimInput,
        latency_ms: 0,
        model_used: 'fallback'
      });
    } finally {
      setLoading(false);
    }
  };

  const handleReviewDraft = async () => {
    if (!draftInput.trim()) return;
    setLoading(true);
    setReviewResult(null);
    try {
      const res = await fetch('/api/compliance/review', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ draft: draftInput })
      });
      const data = await res.json();
      setReviewResult(data);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const handleSendCopilot = async (e) => {
    e.preventDefault();
    if (!copilotInput.trim() || loading) return;
    const query = copilotInput;
    setCopilotInput('');
    setMessages(prev => [...prev, { role: 'user', text: query }]);
    setLoading(true);

    try {
      const res = await fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query })
      });
      const data = await res.json();
      setMessages(prev => [...prev, {
        role: 'assistant',
        text: data.answer || 'Research complete.',
        citations: data.citations || []
      }]);
    } catch (err) {
      setMessages(prev => [...prev, {
        role: 'assistant',
        text: 'Error connecting to Sentinel agent research service.',
        citations: []
      }]);
    } finally {
      setLoading(false);
    }
  };

  const copyToClipboard = (text) => {
    navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const renderBadgeIcon = (label) => {
    switch (label) {
      case 'COMPLIANT':
        return <CheckCircle2 size={18} color="#10b981" />;
      case 'ADVICE_VIOLATION':
        return <AlertOctagon size={18} color="#ef4444" />;
      case 'NEEDS_DISCLAIMER':
        return <AlertTriangle size={18} color="#f59e0b" />;
      case 'UNSUPPORTED':
        return <HelpCircle size={18} color="#8b5cf6" />;
      default:
        return <ShieldCheck size={18} />;
    }
  };

  return (
    <div className="app-container">
      {/* Top Header */}
      <header className="app-header">
        <div className="brand-section">
          <div className="brand-logo-badge">
            <ShieldCheck size={26} />
          </div>
          <div>
            <h1 className="brand-title">Sentinel AI Studio</h1>
            <p className="brand-subtitle">SEBI Compliance & Equity Research Agent Copilot</p>
          </div>
        </div>

        <div className="header-meta">
          <div className="meta-pill">
            <span className="status-dot"></span>
            <span>API Online</span>
          </div>
          <a 
            href="https://huggingface.co/kishanaik5/sentinel-compliance-qwen25-7b-lora" 
            target="_blank" 
            rel="noreferrer"
            className="meta-pill"
          >
            <Cpu size={14} />
            <span>Qwen-2.5-7B LoRA</span>
            <ExternalLink size={12} />
          </a>
        </div>
      </header>

      {/* KPI Stats Strip */}
      <div className="stats-strip">
        <div className="stat-card">
          <div className="stat-value">99.63%</div>
          <div className="stat-label">Empirical Macro F1</div>
        </div>
        <div className="stat-card">
          <div className="stat-value">240ms</div>
          <div className="stat-label">Inference Latency (p50)</div>
        </div>
        <div className="stat-card">
          <div className="stat-value">4 Classes</div>
          <div className="stat-label">SEBI Taxonomy Taxonomy</div>
        </div>
        <div className="stat-card">
          <div className="stat-value">$0.0003</div>
          <div className="stat-label">Cost Per Query</div>
        </div>
      </div>

      {/* Navigation Tabs */}
      <div className="nav-tabs">
        <button 
          id="tab-claim-btn"
          className={`nav-tab-btn ${activeTab === 'claim' ? 'active' : ''}`}
          onClick={() => setActiveTab('claim')}
        >
          <ShieldCheck size={16} />
          Claim Classifier
        </button>
        <button 
          id="tab-draft-btn"
          className={`nav-tab-btn ${activeTab === 'draft' ? 'active' : ''}`}
          onClick={() => setActiveTab('draft')}
        >
          <FileText size={16} />
          Research Draft Auditor
        </button>
        <button 
          id="tab-copilot-btn"
          className={`nav-tab-btn ${activeTab === 'copilot' ? 'active' : ''}`}
          onClick={() => setActiveTab('copilot')}
        >
          <Sparkles size={16} />
          Agent Copilot Chat
        </button>
        <button 
          id="tab-benchmarks-btn"
          className={`nav-tab-btn ${activeTab === 'benchmarks' ? 'active' : ''}`}
          onClick={() => setActiveTab('benchmarks')}
        >
          <Activity size={16} />
          Benchmarks & Architecture
        </button>
      </div>

      {/* ──────────────── TAB 1: CLAIM AUDITOR ──────────────── */}
      {activeTab === 'claim' && (
        <div className="main-grid">
          {/* Left Input Panel */}
          <div className="glass-panel">
            <div className="panel-header">
              <div>
                <h2 className="panel-title">
                  <ShieldCheck size={20} color="#06b6d4" />
                  SEBI Claim Compliance Classifier
                </h2>
                <p className="panel-subtitle">Evaluate individual financial statements against regulatory guidelines.</p>
              </div>
            </div>

            <label className="input-label" htmlFor="claim-textarea">Financial Claim or Sentence to Audit:</label>
            <textarea 
              id="claim-textarea"
              className="custom-textarea"
              value={claimInput}
              onChange={(e) => setClaimInput(e.target.value)}
              placeholder="e.g. Investors should buy Tata Motors immediately with a target price of ₹1200..."
              rows={4}
            />

            {/* Presets */}
            <div className="presets-container">
              <div className="presets-label">Quick Test Presets (from FY25/26 banking dataset):</div>
              <div className="presets-grid">
                {PRESET_CLAIMS.map((p, idx) => (
                  <button 
                    key={idx}
                    id={`preset-claim-${idx}`}
                    className="preset-chip"
                    onClick={() => {
                      setClaimInput(p.claim);
                      setClaimResult(null);
                    }}
                  >
                    <span>{p.category}</span>
                  </button>
                ))}
              </div>
            </div>

            <button 
              id="classify-claim-btn"
              className="btn-primary" 
              onClick={handleClassifyClaim}
              disabled={loading || !claimInput.trim()}
            >
              {loading ? (
                <>
                  <Activity size={18} className="spinner" />
                  <span>Auditing with Qwen-2.5-7B LoRA...</span>
                </>
              ) : (
                <>
                  <ShieldCheck size={18} />
                  <span>Audit Claim Compliance</span>
                </>
              )}
            </button>

            {/* SEBI Taxonomy Info Grid */}
            <div className="taxonomy-grid">
              <div className="taxonomy-card">
                <div className="taxonomy-card-title" style={{ color: '#10b981' }}>
                  <CheckCircle2 size={14} /> COMPLIANT
                </div>
                <div className="taxonomy-card-desc">Factual, verified statements with appropriate regulatory citations.</div>
              </div>
              <div className="taxonomy-card">
                <div className="taxonomy-card-title" style={{ color: '#ef4444' }}>
                  <AlertOctagon size={14} /> ADVICE_VIOLATION
                </div>
                <div className="taxonomy-card-desc">Illegal direct buy/sell investment advice or speculative target prices.</div>
              </div>
              <div className="taxonomy-card">
                <div className="taxonomy-card-title" style={{ color: '#f59e0b' }}>
                  <AlertTriangle size={14} /> NEEDS_DISCLAIMER
                </div>
                <div className="taxonomy-card-desc">Forward-looking projections requiring mandatory statutory warnings.</div>
              </div>
              <div className="taxonomy-card">
                <div className="taxonomy-card-title" style={{ color: '#8b5cf6' }}>
                  <HelpCircle size={14} /> UNSUPPORTED
                </div>
                <div className="taxonomy-card-desc">Material corporate assertions lacking audited disclosures in filings.</div>
              </div>
            </div>
          </div>

          {/* Right Result Panel */}
          <div className="glass-panel">
            <div className="panel-header">
              <div>
                <h2 className="panel-title">
                  <Activity size={20} color="#38bdf8" />
                  Model Inference & Regulatory Output
                </h2>
                <p className="panel-subtitle">Fine-tuned model output, classification label, and compliant rewrite.</p>
              </div>
            </div>

            {claimResult ? (
              <div id="claim-result-container">
                <div className={`result-status-banner banner-${claimResult.label}`}>
                  <div className="status-badge-lg">
                    {renderBadgeIcon(claimResult.label)}
                    <span>{claimResult.label}</span>
                  </div>
                  <div className="latency-tag">
                    ⚡ {claimResult.latency_ms}ms · {claimResult.model_used}
                  </div>
                </div>

                <div className="result-section">
                  <div className="result-section-title">Regulatory Explanation & Reasoning:</div>
                  <div className="result-text-box">
                    {claimResult.explanation}
                  </div>
                </div>

                <div className="result-section">
                  <div className="result-section-title">SEBI-Compliant Sanitized Rewrite:</div>
                  <div className="result-text-box rewrite-box">
                    {claimResult.rewrite}
                  </div>
                  <button 
                    className="preset-chip" 
                    style={{ marginTop: '10px' }}
                    onClick={() => copyToClipboard(claimResult.rewrite)}
                  >
                    {copied ? <Check size={14} color="#10b981" /> : <Copy size={14} />}
                    <span>{copied ? 'Copied Rewrite' : 'Copy Compliant Text'}</span>
                  </button>
                </div>
              </div>
            ) : (
              <div style={{ textAlign: 'center', padding: '60px 20px', color: 'var(--text-muted)' }}>
                <Cpu size={48} style={{ opacity: 0.3, marginBottom: '14px' }} />
                <p style={{ fontSize: '0.95rem' }}>Select a preset or enter a statement on the left and click <strong>Audit Claim Compliance</strong> to inspect the fine-tuned model's output in real time.</p>
              </div>
            )}
          </div>
        </div>
      )}

      {/* ──────────────── TAB 2: DRAFT REVIEWER ──────────────── */}
      {activeTab === 'draft' && (
        <div className="main-grid">
          <div className="glass-panel">
            <div className="panel-header">
              <div>
                <h2 className="panel-title">
                  <FileText size={20} color="#06b6d4" />
                  Full Research Brief Scanner
                </h2>
                <p className="panel-subtitle">Multi-sentence parsing, risk isolation, and automated disclaimer insertion.</p>
              </div>
            </div>

            <label className="input-label" htmlFor="draft-textarea">Research Draft / Analyst Report:</label>
            <textarea 
              id="draft-textarea"
              className="custom-textarea"
              value={draftInput}
              onChange={(e) => setDraftInput(e.target.value)}
              rows={8}
            />

            <button 
              id="review-draft-btn"
              className="btn-primary" 
              style={{ marginTop: '16px' }}
              onClick={handleReviewDraft}
              disabled={loading || !draftInput.trim()}
            >
              {loading ? (
                <>
                  <Activity size={18} className="spinner" />
                  <span>Auditing full research document...</span>
                </>
              ) : (
                <>
                  <FileText size={18} />
                  <span>Scan Entire Report</span>
                </>
              )}
            </button>
          </div>

          <div className="glass-panel">
            <div className="panel-header">
              <div>
                <h2 className="panel-title">
                  <ShieldCheck size={20} color="#10b981" />
                  Audited & Sanitized Document
                </h2>
                <p className="panel-subtitle">Clean regulatory draft ready for publication.</p>
              </div>
              {reviewResult && (
                <button 
                  className="preset-chip"
                  onClick={() => copyToClipboard(reviewResult.audited_text)}
                >
                  {copied ? <Check size={14} color="#10b981" /> : <Copy size={14} />}
                  <span>Copy Report</span>
                </button>
              )}
            </div>

            {reviewResult ? (
              <div>
                <div className={`result-status-banner ${reviewResult.has_violations ? 'banner-ADVICE_VIOLATION' : 'banner-COMPLIANT'}`}>
                  <div className="status-badge-lg">
                    {reviewResult.has_violations ? <AlertOctagon size={18} /> : <CheckCircle2 size={18} />}
                    <span>{reviewResult.compliance_summary}</span>
                  </div>
                  <div className="latency-tag">
                    {reviewResult.claims_evaluated} statements audited
                  </div>
                </div>

                <div className="result-section">
                  <div className="result-section-title">Sanitized Publication Text:</div>
                  <div className="result-text-box rewrite-box" style={{ whiteSpace: 'pre-line' }}>
                    {reviewResult.audited_text}
                  </div>
                </div>

                <div className="result-section">
                  <div className="result-section-title">Sentence-by-Sentence Audit Trace:</div>
                  <div className="audit-trace-list">
                    {reviewResult.audit_trace.map((item, i) => (
                      <div key={i} className="audit-trace-item">
                        <div className="audit-trace-header">
                          <span className={`audit-tag banner-${item.label}`}>{item.label}</span>
                          <span className="latency-tag">{item.latency_ms}ms</span>
                        </div>
                        <div className="audit-claim-text">{item.explanation}</div>
                        {item.rewrite && (
                          <div className="audit-rewrite-text">
                            <strong>Compliant:</strong> {item.rewrite}
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            ) : (
              <div style={{ textAlign: 'center', padding: '60px 20px', color: 'var(--text-muted)' }}>
                <FileText size={48} style={{ opacity: 0.3, marginBottom: '14px' }} />
                <p>Click <strong>Scan Entire Report</strong> to parse each statement in the draft and generate a fully compliant brief with disclaimers.</p>
              </div>
            )}
          </div>
        </div>
      )}

      {/* ──────────────── TAB 3: AGENT COPILOT ──────────────── */}
      {activeTab === 'copilot' && (
        <div className="glass-panel" style={{ maxWidth: '900px', margin: '0 auto' }}>
          <div className="panel-header">
            <div>
              <h2 className="panel-title">
                <Sparkles size={20} color="#38bdf8" />
                Sentinel Agentic Copilot Chat
              </h2>
              <p className="panel-subtitle">End-to-end LangGraph equity research with real-time compliance validation.</p>
            </div>
          </div>

          <div className="chat-window">
            {messages.map((m, idx) => (
              <div key={idx} className={`chat-bubble ${m.role === 'user' ? 'chat-user' : 'chat-assistant'}`}>
                <div>{m.text}</div>
                {m.citations && m.citations.length > 0 && (
                  <div style={{ marginTop: '8px' }}>
                    {m.citations.map((c, i) => (
                      <span key={i} className="citation-pill">
                        📑 {c.company || 'BSE/NSE'} p.{c.page || '1'}
                      </span>
                    ))}
                  </div>
                )}
              </div>
            ))}
            {loading && (
              <div className="chat-bubble chat-assistant" style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <Activity size={16} className="spinner" />
                <span>Sentinel is researching annual filings & checking compliance...</span>
              </div>
            )}
          </div>

          <form onSubmit={handleSendCopilot} style={{ display: 'flex', gap: '10px' }}>
            <input 
              id="copilot-input"
              type="text" 
              className="custom-textarea" 
              style={{ minHeight: 'unset', height: '48px' }}
              value={copilotInput}
              onChange={(e) => setCopilotInput(e.target.value)}
              placeholder="Ask an Indian equity research question (e.g. What is TCS FY2025 revenue?)..."
            />
            <button 
              id="copilot-send-btn"
              type="submit" 
              className="btn-primary" 
              style={{ width: 'auto', padding: '0 20px' }}
              disabled={loading || !copilotInput.trim()}
            >
              <Send size={18} />
            </button>
          </form>
        </div>
      )}

      {/* ──────────────── TAB 4: BENCHMARKS ──────────────── */}
      {activeTab === 'benchmarks' && (
        <div className="glass-panel" style={{ maxWidth: '980px', margin: '0 auto' }}>
          <div className="panel-header">
            <div>
              <h2 className="panel-title">
                <Activity size={20} color="#06b6d4" />
                Empirical Benchmark Comparison
              </h2>
              <p className="panel-subtitle">Fine-tuned Qwen-2.5-7B LoRA vs Frontier LLM Baselines across 271 held-out test claims.</p>
            </div>
          </div>

          <div style={{ overflowX: 'auto', margin: '16px 0 24px' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '0.9rem' }}>
              <thead>
                <tr style={{ borderBottom: '1px solid var(--border-subtle)', color: 'var(--text-muted)' }}>
                  <th style={{ padding: '12px' }}>Model / Adapter</th>
                  <th style={{ padding: '12px' }}>Macro F1</th>
                  <th style={{ padding: '12px' }}>Accuracy</th>
                  <th style={{ padding: '12px' }}>Latency (p50)</th>
                  <th style={{ padding: '12px' }}>Cost / 1k Queries</th>
                  <th style={{ padding: '12px' }}>Deployment</th>
                </tr>
              </thead>
              <tbody>
                <tr style={{ background: 'rgba(6, 182, 212, 0.08)', fontWeight: 600 }}>
                  <td style={{ padding: '12px', color: '#38bdf8' }}>Qwen-2.5-7B LoRA (Fine-Tuned)</td>
                  <td style={{ padding: '12px', color: '#34d399' }}>0.9963</td>
                  <td style={{ padding: '12px', color: '#34d399' }}>99.63%</td>
                  <td style={{ padding: '12px' }}>240ms</td>
                  <td style={{ padding: '12px' }}>$0.30</td>
                  <td style={{ padding: '12px' }}>Hugging Face / vLLM</td>
                </tr>
                <tr style={{ borderBottom: '1px solid var(--border-subtle)' }}>
                  <td style={{ padding: '12px' }}>GPT-4o-mini (Zero-Shot)</td>
                  <td style={{ padding: '12px' }}>0.8412</td>
                  <td style={{ padding: '12px' }}>85.24%</td>
                  <td style={{ padding: '12px' }}>850ms</td>
                  <td style={{ padding: '12px' }}>$1.80</td>
                  <td style={{ padding: '12px' }}>OpenAI API</td>
                </tr>
                <tr style={{ borderBottom: '1px solid var(--border-subtle)' }}>
                  <td style={{ padding: '12px' }}>Qwen-2.5-7B (Base Zero-Shot)</td>
                  <td style={{ padding: '12px' }}>0.5830</td>
                  <td style={{ padding: '12px' }}>61.25%</td>
                  <td style={{ padding: '12px' }}>480ms</td>
                  <td style={{ padding: '12px' }}>$0.30</td>
                  <td style={{ padding: '12px' }}>Hugging Face Base</td>
                </tr>
              </tbody>
            </table>
          </div>

          <div className="presets-grid" style={{ justifyContent: 'center', marginTop: '20px' }}>
            <a 
              href="https://huggingface.co/kishanaik5/sentinel-compliance-qwen25-7b-lora" 
              target="_blank" 
              rel="noreferrer"
              className="meta-pill"
              style={{ padding: '8px 16px', fontSize: '0.85rem' }}
            >
              <Cpu size={16} />
              <span>Hugging Face Model Weights & Model Card</span>
              <ExternalLink size={14} />
            </a>
            <a 
              href="https://www.kaggle.com/datasets/kishanknaik/finetuning-banking-fy-25-26-dataset" 
              target="_blank" 
              rel="noreferrer"
              className="meta-pill"
              style={{ padding: '8px 16px', fontSize: '0.85rem' }}
            >
              <Layers size={16} />
              <span>Kaggle Banking FY25/26 Dataset</span>
              <ExternalLink size={14} />
            </a>
          </div>
        </div>
      )}
    </div>
  );
}
