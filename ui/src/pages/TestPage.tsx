import { useState, useEffect, useRef } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api/client";
import type { GenerateResponse, GenerateStep as GenerateStepT, CsvPreview, EvalEntry } from "../types";

type GenType = GenerateStepT["type"];

const ALL_TYPES: GenType[] = ["upload", "stage1", "stage2", "synthetic"];

const TYPE_LABELS: Record<GenType, string> = {
  upload: "Clean Upload",
  stage1: "Stage 1 Fraud",
  stage2: "Stage 2 Triage",
  synthetic: "Synthetic Fraud Patterns",
};

const TYPE_DESCS: Record<GenType, string> = {
  upload: "Standard upload CSV with optional bad rows",
  stage1: "Transactions that trigger deterministic rules",
  stage2: "Scenario-based transactions for LLM triage evaluation",
  synthetic: "5 fraud patterns (structuring, velocity, travel, round-trip, watchlist) with clean txns",
};

const INITIAL_COUNTS: Record<GenType, number> = {
  upload: 1000,
  stage1: 200,
  stage2: 20,
  synthetic: 500,
};

function todayStr() {
  return new Date().toISOString().slice(0, 10);
}

type PreviewTab = "csv" | "eval";

export default function TestPage() {
  const navigate = useNavigate();
  const resultRef = useRef<HTMLDivElement>(null);
  const [enabled, setEnabled] = useState<Record<GenType, boolean>>({
    upload: true,
    stage1: false,
    stage2: false,
    synthetic: false,
  });
  const [counts, setCounts] = useState({ ...INITIAL_COUNTS });
  const [badRows, setBadRows] = useState(50);
  const [shuffle, setShuffle] = useState(true);
  const [date, setDate] = useState(todayStr());
  const [generating, setGenerating] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [result, setResult] = useState<GenerateResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [previewTab, setPreviewTab] = useState<PreviewTab>("csv");
  const [csvPreview, setCsvPreview] = useState<CsvPreview | null>(null);
  const [evalEntries, setEvalEntries] = useState<EvalEntry[] | null>(null);
  const [previewError, setPreviewError] = useState<string | null>(null);

  const totalRows = ALL_TYPES
    .filter(t => enabled[t])
    .reduce((sum, t) => sum + counts[t], 0);

  const handleGenerate = async () => {
    setGenerating(true);
    setError(null);
    setResult(null);
    setCsvPreview(null);
    setEvalEntries(null);
    setPreviewError(null);
    try {
      const steps = ALL_TYPES
        .filter(t => enabled[t])
        .map(t => ({
          type: t,
          count: counts[t],
          bad_rate: t === "upload" ? badRows : 0,
        }));
      const res = await api.post<GenerateResponse>("/api/generate", {
        steps,
        shuffle,
        date: date || null,
      });
      setResult(res);

      const [csvData, evalData] = await Promise.all([
        res.download_url
          ? api.get<CsvPreview>(res.download_url.replace("/download/", "/preview/")).catch(() => null)
          : Promise.resolve(null),
        res.eval_url
          ? api.get<EvalEntry[]>(res.eval_url).catch(() => null)
          : Promise.resolve(null),
      ]);
      if (csvData) setCsvPreview(csvData);
      if (evalData) setEvalEntries(evalData);
      if (!csvData) setPreviewError("Could not load CSV preview");
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Generation failed");
    } finally {
      setGenerating(false);
    }
  };

  const handleUpload = async () => {
    if (!result) return;
    setUploading(true);
    try {
      await api.post(`/api/uploads/from-work/${result.filename}`);
      navigate("/operations?tab=search");
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Upload failed");
    } finally {
      setUploading(false);
    }
  };

  const toggle = (t: GenType) => setEnabled(prev => ({ ...prev, [t]: !prev[t] }));
  const setCount = (t: GenType, v: number) => setCounts(prev => ({ ...prev, [t]: Math.max(1, v) }));

  useEffect(() => {
    if (result && resultRef.current) {
      resultRef.current.scrollIntoView({ behavior: "smooth", block: "start" });
    }
  }, [result]);

  useEffect(() => { setPreviewTab("csv"); }, [result]);

  const resultSection = result && (
    <div ref={resultRef} className="bg-white border border-slate-200 rounded-lg p-5 space-y-4">
      <div className="flex items-center gap-2">
        <span className="text-lg">&#9989;</span>
        <span className="text-sm font-medium text-slate-700">File generated successfully</span>
      </div>

      <div className="flex gap-1 bg-slate-100 rounded-lg p-1 w-fit">
        <button onClick={() => setPreviewTab("csv")}
          className={`px-4 py-1.5 text-xs font-medium rounded-md transition-colors ${
            previewTab === "csv" ? "bg-white text-slate-800 shadow-sm" : "text-slate-500 hover:text-slate-700"
          }`}>
          CSV File
        </button>
        <button onClick={() => setPreviewTab("eval")} disabled={!evalEntries}
          className={`px-4 py-1.5 text-xs font-medium rounded-md transition-colors ${
            !evalEntries ? "text-slate-300 cursor-not-allowed" :
            previewTab === "eval" ? "bg-white text-slate-800 shadow-sm" : "text-slate-500 hover:text-slate-700"
          }`}>
          Eval Data
        </button>
      </div>

      {previewTab === "csv" && (
        <div className="max-h-80 overflow-auto border border-slate-200 rounded-lg">
          {csvPreview ? (
            <table className="w-full text-xs">
              <thead className="bg-slate-50 sticky top-0">
                <tr>
                  {csvPreview.fieldnames.map(f => (
                    <th key={f} className="px-3 py-2 text-left font-medium text-slate-600 whitespace-nowrap border-b border-slate-200">{f}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {csvPreview.rows.map((row, i) => (
                  <tr key={i} className={i % 2 === 0 ? "bg-white" : "bg-slate-50/50"}>
                    {csvPreview.fieldnames.map(f => (
                      <td key={f} className="px-3 py-1.5 text-slate-700 border-b border-slate-100 whitespace-nowrap">{row[f] ?? ""}</td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <div className="p-4 text-sm text-slate-400">
              {previewError ? (
                <span className="text-amber-600">{previewError}</span>
              ) : (
                "Loading preview..."
              )}
            </div>
          )}
        </div>
      )}

      {previewTab === "eval" && evalEntries && (
        <div className="max-h-80 overflow-auto border border-slate-200 rounded-lg">
          <table className="w-full text-xs">
            <thead className="bg-slate-50 sticky top-0">
              <tr>
                <th className="px-3 py-2 text-left font-medium text-slate-600 border-b border-slate-200">source_txn_id</th>
                <th className="px-3 py-2 text-left font-medium text-slate-600 border-b border-slate-200">scenario</th>
                <th className="px-3 py-2 text-left font-medium text-slate-600 border-b border-slate-200">expected_escalate</th>
                <th className="px-3 py-2 text-left font-medium text-slate-600 border-b border-slate-200">ground_truth</th>
                <th className="px-3 py-2 text-left font-medium text-slate-600 border-b border-slate-200">reason_hint</th>
              </tr>
            </thead>
            <tbody>
              {evalEntries.map((entry, i) => (
                <tr key={i} className={i % 2 === 0 ? "bg-white" : "bg-slate-50/50"}>
                  <td className="px-3 py-1.5 font-mono text-slate-700 border-b border-slate-100">{entry.source_txn_id}</td>
                  <td className="px-3 py-1.5 text-slate-700 border-b border-slate-100">{entry.scenario}</td>
                  <td className="px-3 py-1.5 border-b border-slate-100">
                    <span className={`inline-flex px-1.5 py-0.5 text-xs font-medium rounded ${
                      entry.expected_escalate ? "bg-red-100 text-red-700" : "bg-green-100 text-green-700"
                    }`}>
                      {entry.expected_escalate ? "YES" : "no"}
                    </span>
                  </td>
                  <td className="px-3 py-1.5 text-slate-700 border-b border-slate-100">{entry.ground_truth}</td>
                  <td className="px-3 py-1.5 text-slate-500 border-b border-slate-100">{entry.reason_hint}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <div className="flex gap-3 pt-2">
        <button onClick={() => api.download(result.download_url)}
          className="px-4 py-2 bg-green-600 text-white rounded-lg text-sm font-medium hover:bg-green-700 transition-colors">
          Download CSV
        </button>
        <button onClick={handleUpload} disabled={uploading}
          className="px-4 py-2 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700 disabled:opacity-60 disabled:cursor-not-allowed transition-colors flex items-center gap-2">
          {uploading ? (
            <>
              <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
              Uploading...
            </>
          ) : (
            "Upload to Pipeline"
          )}
        </button>
      </div>
    </div>
  );

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-3">
        <h2 className="text-xl font-bold text-slate-800">Test Data Generator</h2>
        <span className="inline-flex items-center px-2 py-0.5 text-xs font-bold bg-amber-100 text-amber-700 rounded-full border border-amber-300">
          DEV ONLY
        </span>
      </div>

      <div className="flex items-start gap-3 bg-amber-50 border border-amber-200 rounded-lg p-4 text-sm text-amber-800">
        <span className="text-lg leading-none mt-0.5">&#9888;&#65039;</span>
        <div>
          <strong>Development-only tool.</strong> This generator runs arbitrary scripts
          against the database and application code. Do not use in production environments.
        </div>
      </div>

      <div className="bg-white border border-slate-200 rounded-lg p-5 space-y-3">
        {ALL_TYPES.map(t => {
          const isOn = enabled[t];
          return (
          <div key={t} className={`flex items-center gap-3 p-3 rounded-lg border transition-colors ${
            isOn ? "bg-slate-50 border-slate-200" : "bg-white border-dashed border-slate-300"
          }`}>
            <input type="checkbox" checked={isOn} onChange={() => toggle(t)}
              className="rounded border-slate-300 text-blue-600 focus:ring-blue-500 shrink-0" />
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-3 flex-wrap">
                <label className="text-sm font-medium text-slate-700 cursor-pointer" onClick={() => toggle(t)}>
                  {TYPE_LABELS[t]}
                </label>
                {!isOn && <span className="text-xs text-slate-400 italic">(tick to add)</span>}
                <input type="number" min={1} max={100000} value={counts[t]}
                  onChange={e => setCount(t, Number(e.target.value))}
                  className="w-24 px-2 py-1 border border-slate-300 rounded text-xs focus:outline-none focus:ring-1 focus:ring-blue-500" />
                {t === "upload" && (
                  <>
                    <span className="text-xs text-slate-400">bad rows</span>
                    <input type="number" min={0} max={100000} value={badRows}
                      onChange={e => setBadRows(Math.max(0, Number(e.target.value)))}
                      className="w-20 px-2 py-1 border border-slate-300 rounded text-xs focus:outline-none focus:ring-1 focus:ring-blue-500" />
                  </>
                )}
              </div>
              <p className="text-xs mt-0.5 text-slate-400">{TYPE_DESCS[t]}</p>
            </div>
          </div>
          );
        })}

        <div className="flex gap-6 items-center pt-1">
          <label className="flex items-center gap-2 text-sm text-slate-700 cursor-pointer">
            <input type="checkbox" checked={shuffle} onChange={e => setShuffle(e.target.checked)}
              className="rounded border-slate-300 text-blue-600 focus:ring-blue-500" />
            Shuffle after generation
          </label>
          <div>
            <label className="text-sm text-slate-500 mr-2">Date</label>
            <input type="date" value={date}
              onChange={e => setDate(e.target.value)}
              className="px-2 py-1.5 border border-slate-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500" />
          </div>
        </div>

        <div className="text-right text-sm text-slate-500 pt-1">
          Total rows: <strong className="text-slate-800">{totalRows.toLocaleString()}</strong>
        </div>

        <button onClick={handleGenerate} disabled={generating || totalRows === 0}
          className="w-full py-2.5 px-4 bg-blue-600 text-white rounded-lg font-medium text-sm hover:bg-blue-700 disabled:opacity-60 disabled:cursor-not-allowed transition-colors flex items-center justify-center gap-2">
          {generating ? (
            <>
              <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
              Generating...
            </>
          ) : (
            "Generate"
          )}
        </button>
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-4 text-sm text-red-700">{error}</div>
      )}

      {resultSection}
    </div>
  );
}
