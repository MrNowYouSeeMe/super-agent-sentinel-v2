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

const API_BASE = "http://127.0.0.1:8000/api/v1";

export default function App() {
  const [scenarios, setScenarios] = useState<Scenario[]>([]);
  const [activeId, setActiveId] = useState("hidden_provider_shortage");
  const [result, setResult] = useState<Result | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    fetch(`${API_BASE}/demo/scenarios`)
      .then((response) => response.json())
      .then(setScenarios)
      .catch(() => setError("Backend scenario API unavailable."));
  }, []);

  async function runScenario(id = activeId) {
    setLoading(true);
    setError("");
    try {
      const response = await fetch(`${API_BASE}/demo/scenarios/${id}`, {
        method: "POST",
      });
      if (!response.ok) throw new Error(`API returned ${response.status}`);
      setResult(await response.json());
      setActiveId(id);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unknown error");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main>
      <header>
        <p className="eyebrow">SUPERAGENT SENTINEL V2 · LOCAL DEMO</p>
        <h1>Multi-provider MFS liquidity and anomaly decision support</h1>
        <p>
          Shared physical cash stays separate from bKash, Nagad, and Rocket balances.
          The system estimates provider-specific shortage windows, reduces confidence
          when data is stale or conflicting, and routes only safe human-review actions.
        </p>
      </header>

      <section className="card scenario-card">
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
              <div><dt>Confidence</dt><dd>{Math.round(result.analysis.decision.confidence * 100)}%</dd></div>
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

