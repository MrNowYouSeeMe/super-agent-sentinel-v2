import { useState } from "react";

const demoPayload = {
  outlet_id: "OUT-SYL-017",
  area_id: "sylhet",
  language: "banglish",
  festival_or_market_day: true,
  shared_cash: {
    resource_id: "shared_cash",
    balance: 100000,
    safe_buffer: 20000,
    cash_in_5m: 40000,
    cash_out_5m: 25000,
  },
  providers: [
    {
      resource_id: "bkash",
      balance: 7000,
      safe_buffer: 2000,
      cash_in_5m: 1000,
      cash_out_5m: 26000,
      transaction_count_5m: 30,
      repeated_amount_ratio: 0.8,
      unique_customer_ratio: 0.2,
      failure_rate: 0.05,
      feed_age_seconds: 180,
      reconciliation_difference: 0,
    },
    {
      resource_id: "nagad",
      balance: 120000,
      safe_buffer: 15000,
      cash_in_5m: 25000,
      cash_out_5m: 20000,
    },
    {
      resource_id: "rocket",
      balance: 90000,
      safe_buffer: 15000,
      cash_in_5m: 18000,
      cash_out_5m: 17000,
    },
  ],
};

type Result = {
  decision: {
    classification: string;
    severity: string;
    affected_resource: string;
    confidence: number;
    human_review_required: boolean;
    recommended_action: string;
  };
  explanation: string;
  evidence: string[];
};

export default function App() {
  const [result, setResult] = useState<Result | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function runDemo() {
    setLoading(true);
    setError("");
    try {
      const response = await fetch("http://127.0.0.1:8000/api/v1/intelligence/analyze", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(demoPayload),
      });
      if (!response.ok) throw new Error(`API returned ${response.status}`);
      setResult(await response.json());
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unknown error");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main>
      <header>
        <p className="eyebrow">MULTI-PROVIDER MFS DECISION SUPPORT</p>
        <h1>SuperAgent Sentinel V2</h1>
        <p>Shared cash and provider balances remain separate. Every material case stays human-controlled.</p>
      </header>

      <section className="grid">
        <article className="card">
          <h2>Demo scenario</h2>
          <p>Healthy shared cash, but rapidly depleting bKash e-money with repeated transaction patterns.</p>
          <button onClick={runDemo} disabled={loading}>
            {loading ? "Analyzing…" : "Run local analysis"}
          </button>
          {error && <p className="error">{error}</p>}
        </article>

        <article className="card">
          <h2>Decision</h2>
          {!result ? (
            <p>No analysis has been run.</p>
          ) : (
            <>
              <dl>
                <div><dt>Resource</dt><dd>{result.decision.affected_resource}</dd></div>
                <div><dt>Classification</dt><dd>{result.decision.classification}</dd></div>
                <div><dt>Severity</dt><dd>{result.decision.severity}</dd></div>
                <div><dt>Confidence</dt><dd>{Math.round(result.decision.confidence * 100)}%</dd></div>
              </dl>
              <p className="explanation">{result.explanation}</p>
            </>
          )}
        </article>
      </section>

      {result && (
        <section className="card evidence">
          <h2>Evidence</h2>
          <ul>{result.evidence.map((item) => <li key={item}>{item}</li>)}</ul>
        </section>
      )}
    </main>
  );
}
