import { useEffect, useState } from "react";

type Scenario = {
  scenario_id: string;
  title: string;
  purpose: string;
};

type CaseEvent = {
  sequence: number;
  status: string;
  actor_role: string;
  event: string;
  note: string;
};

type ResourceAnalysis = {
  resource_id: string;
  data_quality: { state: string; score: number };
  liquidity: {
    estimated_runway_minutes: number | null;
    shortage_eta_low_minutes: number | null;
    shortage_eta_high_minutes: number | null;
    shortage_probability_60m: number;
    confidence: number;
  };
  anomaly: { score: number };
  ml_prediction: {
    model_version: string;
    anomaly_probability: number;
    shortage_probability_60m: number;
    notable_signals: string[];
  };
  fused_shortage_probability_60m: number;
  fused_anomaly_score: number;
  fused_confidence: number;
};

type Result = {
  scenario: Scenario;
  analysis: {
    decision: {
      classification: string;
      severity: string;
      affected_resource: string;
      confidence: number;
      human_review_required: boolean;
      recommended_action: string;
      safe_boundary: string;
    };
    resources: ResourceAnalysis[];
    explanation: string;
    evidence: string[];
    possible_normal_context: string[];
  };
  case: null | {
    case_id: string;
    current_status: string;
    owner_role: string;
    audit_summary: string;
    timeline: CaseEvent[];
  };
};

type ModelStatus = {
  available: boolean;
  model_version: string | null;
  phase6c_metrics_available: boolean;
  openai_enabled: boolean;
  openai_key_configured: boolean;
  safety_boundary: string;
};

type TrainedPrediction = {
  model_version: string;
  classification: string;
  severity: string;
  affected_resource: string;
  probabilities: {
    anomaly: number;
    shortage_30m: number;
    shortage_60m: number;
    shortage_120m: number;
  };
  estimated_time_to_shortage_minutes: number | null;
  confidence: number;
  data_health: string;
  human_review_required: boolean;
  primary_stakeholder: string;
  secondary_stakeholder: string;
  stakeholder_visibility: string[];
  evidence: string[];
  recommended_action: string;
  explanation: string;
  explanation_mode: string;
  safety_boundary: string;
};

const API_BASE = "http://127.0.0.1:8000/api/v1";
const pct = (value: number) => `${Math.round(value * 100)}%`;

function runwayText(resource: ResourceAnalysis) {
  const low = resource.liquidity.shortage_eta_low_minutes;
  const high = resource.liquidity.shortage_eta_high_minutes;
  if (low === null || high === null) return "No burn";
  return `${low}-${high} min`;
}

export default function App() {
  const [scenarios, setScenarios] = useState<Scenario[]>([]);
  const [activeId, setActiveId] = useState("hidden_provider_shortage");
  const [result, setResult] = useState<Result | null>(null);
  const [modelStatus, setModelStatus] = useState<ModelStatus | null>(null);
  const [trainedPrediction, setTrainedPrediction] = useState<TrainedPrediction | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [modelLoading, setModelLoading] = useState(false);

  useEffect(() => {
    Promise.all([
      fetch(`${API_BASE}/demo/scenarios`).then((response) => response.json()),
      fetch(`${API_BASE}/ml/phase6b/status`).then((response) => response.json()),
    ])
      .then(([scenarioData, statusData]) => {
        setScenarios(scenarioData);
        setModelStatus(statusData);
      })
      .catch(() => setError("Backend API unavailable."));
  }, []);

  async function runScenario(id = activeId) {
    setLoading(true);
    setError("");
    try {
      const response = await fetch(`${API_BASE}/demo/scenarios/${id}`, { method: "POST" });
      if (!response.ok) throw new Error(`API returned ${response.status}`);
      setResult(await response.json());
      setActiveId(id);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unknown error");
    } finally {
      setLoading(false);
    }
  }

  async function runTrainedModelDemo() {
    setModelLoading(true);
    setError("");
    try {
      const loginResponse = await fetch(`${API_BASE}/auth/demo-login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ profile_id: "area-manager-sylhet" }),
      });
      if (!loginResponse.ok) throw new Error(`Login returned ${loginResponse.status}`);
      const login = await loginResponse.json();

      const predictionResponse = await fetch(`${API_BASE}/ml/phase6b/predict`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${login.access_token}`,
        },
        body: JSON.stringify({
          episode_id: "phase7-ui-demo",
          window_id: "phase7-ui-window",
          timestamp: new Date().toISOString(),
          area_id: "sylhet",
          outlet_id: "OUT-1",
          agent_profile: "high_volume",
          location_type: "urban",
          provider_mix_shift: "bkash_heavy",
          festival_flag: 1,
          salary_flag: 0,
          remittance_flag: 0,
          market_day_flag: 1,
          network_recovery_flag: 0,
          shared_cash_balance: 90000,
          bkash_balance: 7000,
          nagad_balance: 120000,
          rocket_balance: 80000,
          tx_count_5m: 34,
          cash_in_amount_5m: 1000,
          cash_out_amount_5m: 30000,
          net_cash_flow_5m: -29000,
          velocity_vs_baseline: 3.4,
          repeated_amount_ratio: 0.74,
          unique_customer_ratio: 0.18,
          failure_rate: 0.03,
          duplicate_ratio: 0.01,
          missing_ratio: 0,
          out_of_order_ratio: 0,
          feed_age_seconds: 30,
          reconciliation_difference: 0,
          data_quality_score: 0.96,
          shared_cash_burn_15m: 15000,
          shared_cash_burn_30m: 28000,
          shared_cash_burn_60m: 50000,
          bkash_burn_60m: 42000,
          nagad_burn_60m: 5000,
          rocket_burn_60m: 4000,
          language: "banglish",
          use_openai_explanation: false,
        }),
      });
      if (!predictionResponse.ok) {
        const body = await predictionResponse.text();
        throw new Error(`Prediction returned ${predictionResponse.status}: ${body}`);
      }
      setTrainedPrediction(await predictionResponse.json());
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unknown error");
    } finally {
      setModelLoading(false);
    }
  }

  return (
    <main>
      <header>
        <p className="eyebrow">SUPERAGENT SENTINEL V2 · TRAINED LOCAL MODEL</p>
        <h1>Multi-provider MFS liquidity and anomaly decision support</h1>
        <p>
          The trained hybrid model now runs behind validated APIs. It predicts risk and routes
          cases to the correct stakeholder, while human reviewers retain final authority.
        </p>
      </header>

      <section className="card model-status-card">
        <div>
          <p className="eyebrow">PHASE 7 MODEL RUNTIME</p>
          <h2>{modelStatus?.available ? "Trained model ready" : "Model unavailable"}</h2>
          <p className="small-note">
            Version: {modelStatus?.model_version ?? "not loaded"} · Phase 6C metrics:{" "}
            {modelStatus?.phase6c_metrics_available ? "available" : "missing"} · OpenAI:{" "}
            {modelStatus?.openai_enabled && modelStatus?.openai_key_configured
              ? "configured"
              : "deterministic fallback"}
          </p>
        </div>
        <button onClick={runTrainedModelDemo} disabled={modelLoading || !modelStatus?.available}>
          {modelLoading ? "Running trained model..." : "Run trained model demo"}
        </button>
      </section>

      {trainedPrediction && (
        <section className="card trained-result">
          <div className="result-heading">
            <div>
              <p className="eyebrow">VALIDATED MODEL OUTPUT</p>
              <h2>{trainedPrediction.classification}</h2>
            </div>
            <span className={`severity ${trainedPrediction.severity}`}>
              {trainedPrediction.severity}
            </span>
          </div>

          <div className="metric-grid">
            <div><span>Anomaly</span><strong>{pct(trainedPrediction.probabilities.anomaly)}</strong></div>
            <div><span>Shortage 30m</span><strong>{pct(trainedPrediction.probabilities.shortage_30m)}</strong></div>
            <div><span>Shortage 60m</span><strong>{pct(trainedPrediction.probabilities.shortage_60m)}</strong></div>
            <div><span>Shortage 120m</span><strong>{pct(trainedPrediction.probabilities.shortage_120m)}</strong></div>
            <div><span>Affected</span><strong>{trainedPrediction.affected_resource}</strong></div>
            <div><span>ETA</span><strong>{trainedPrediction.estimated_time_to_shortage_minutes === null ? "N/A" : `${Math.round(trainedPrediction.estimated_time_to_shortage_minutes)} min`}</strong></div>
          </div>

          <div className="routing-box">
            <h3>Human stakeholder routing</h3>
            <p><strong>Primary:</strong> {trainedPrediction.primary_stakeholder}</p>
            <p><strong>Secondary:</strong> {trainedPrediction.secondary_stakeholder}</p>
            <p><strong>Visibility:</strong> {trainedPrediction.stakeholder_visibility.join(", ")}</p>
          </div>

          <p className="explanation">{trainedPrediction.explanation}</p>
          <div className="evidence">
            <h3>Evidence</h3>
            <ul>{trainedPrediction.evidence.map((item) => <li key={item}>{item}</li>)}</ul>
          </div>
          <p className="safe-boundary">{trainedPrediction.safety_boundary}</p>
        </section>
      )}

      <section className="card scenario-card">
        <p className="small-note">
          Existing deterministic scenarios remain available for judge-safe rehearsal and fallback.
        </p>
        <h2>Demo scenarios</h2>
        <div className="scenario-grid">
          {scenarios.map((scenario) => (
            <button
              className={scenario.scenario_id === activeId ? "scenario active" : "scenario"}
              key={scenario.scenario_id}
              onClick={() => runScenario(scenario.scenario_id)}
              disabled={loading}
            >
              <strong>{scenario.title}</strong>
              <span>{scenario.purpose}</span>
            </button>
          ))}
        </div>
        {scenarios.length === 0 && <p>Loading scenarios...</p>}
        {error && <p className="error">{error}</p>}
      </section>

      {result && (
        <section className="grid">
          <div className="card">
            <h2>Decision</h2>
            <dl>
              <div><dt>Scenario</dt><dd>{result.scenario.title}</dd></div>
              <div><dt>Classification</dt><dd>{result.analysis.decision.classification}</dd></div>
              <div><dt>Severity</dt><dd>{result.analysis.decision.severity}</dd></div>
              <div><dt>Affected resource</dt><dd>{result.analysis.decision.affected_resource}</dd></div>
              <div><dt>Confidence</dt><dd>{pct(result.analysis.decision.confidence)}</dd></div>
              <div><dt>Human review</dt><dd>{result.analysis.decision.human_review_required ? "Required" : "Not required"}</dd></div>
              <div><dt>Next action</dt><dd>{result.analysis.decision.recommended_action}</dd></div>
            </dl>
            <p className="safe-boundary">{result.analysis.decision.safe_boundary}</p>
          </div>

          <div className="card">
            <h2>Explanation</h2>
            <p className="explanation">{result.analysis.explanation}</p>
            {result.analysis.possible_normal_context.length > 0 && (
              <div className="evidence">
                <h3>Context reducing over-claiming</h3>
                <ul>{result.analysis.possible_normal_context.map((item) => <li key={item}>{item}</li>)}</ul>
              </div>
            )}
            <div className="evidence">
              <h3>Evidence</h3>
              <ul>{result.analysis.evidence.map((item) => <li key={item}>{item}</li>)}</ul>
            </div>
          </div>

          <div className="card wide">
            <h2>Resource-level AI and liquidity scores</h2>
            <div className="resource-table">
              <div className="resource-row heading">
                <span>Resource</span><span>Data</span><span>Runway</span><span>Rule shortage</span><span>ML shortage</span><span>ML anomaly</span><span>Fused confidence</span>
              </div>
              {result.analysis.resources.map((resource) => (
                <div className="resource-row" key={resource.resource_id}>
                  <span>{resource.resource_id}</span>
                  <span>{resource.data_quality.state} · {pct(resource.data_quality.score)}</span>
                  <span>{runwayText(resource)}</span>
                  <span>{pct(resource.liquidity.shortage_probability_60m)}</span>
                  <span>{pct(resource.ml_prediction.shortage_probability_60m)}</span>
                  <span>{pct(resource.ml_prediction.anomaly_probability)}</span>
                  <span>{pct(resource.fused_confidence)}</span>
                </div>
              ))}
            </div>
          </div>

          <div className="card wide">
            <h2>Human-in-the-loop case</h2>
            {!result.case && <p>No case created because the decision is safe to monitor.</p>}
            {result.case && (
              <>
                <dl>
                  <div><dt>Case ID</dt><dd>{result.case.case_id}</dd></div>
                  <div><dt>Status</dt><dd>{result.case.current_status}</dd></div>
                  <div><dt>Owner</dt><dd>{result.case.owner_role}</dd></div>
                </dl>
                <p className="explanation">{result.case.audit_summary}</p>
                <ol className="timeline">
                  {result.case.timeline.map((event) => (
                    <li key={`${event.sequence}-${event.event}`}>
                      <strong>{event.status}</strong> · {event.actor_role}<br />
                      <span>{event.note}</span>
                    </li>
                  ))}
                </ol>
              </>
            )}
          </div>
        </section>
      )}
    </main>
  );
}