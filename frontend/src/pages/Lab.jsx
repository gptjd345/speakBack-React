import React, { useState, useEffect } from "react";
import { useAuth } from "../contexts/AuthContext";
import api from "../utils/api";
import { fetchHistory, prepareAnalysis, runLangGraphRequestStream } from "../api/langgraphApi";
import AudioUploader from "../components/AudioUploader";
import ResultViewer from "../components/ResultViewer";
import "../styles/Lab.css";

// ─── Practice Card ────────────────────────────────────────────────
const PROGRESS_STEPS = [
  { step: 0, label: "Converting audio" },
  { step: 1, label: "Transcribing speech" },
  { step: 2, label: "Acoustic analysis" },
  { step: 3, label: "AI evaluation" },
];

function PracticeCard({ index, sentence, user }) {
  const [file, setFile] = useState(null);
  const [analyzing, setAnalyzing] = useState(false);
  const [analysisStatus, setAnalysisStatus] = useState(null);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);

  const handleAnalyze = async () => {
    if (!file) return;
    setAnalyzing(true);
    setResult(null);
    setError(null);
    setAnalysisStatus(null);
    try {
      let res = null;
      await runLangGraphRequestStream(
        file,
        user,
        sentence,
        (progress) => setAnalysisStatus(progress),
        (result) => { res = result; },
      );
      setResult(res);
    } catch {
      setError("Analysis failed. Please try again.");
    } finally {
      setAnalyzing(false);
      setAnalysisStatus(null);
    }
  };

  return (
    <div className="sb-practice-card">
      <div className="sb-practice-num">
        Practice {index + 1} <span>/ 3</span>
      </div>
      <div className="sb-practice-sentence">"{sentence}"</div>

      <AudioUploader file={file} setFile={setFile} />

      <div className="sb-practice-analyze-row">
        <button
          className="sb-btn sb-btn-primary"
          onClick={handleAnalyze}
          disabled={analyzing || !file}
        >
          {analyzing ? (
            <>
              <span className="sb-spinner" style={{ borderTopColor: "white" }} />
              Analyzing…
            </>
          ) : (
            "✨ Analyze Pronunciation"
          )}
        </button>
      </div>

      {analyzing && analysisStatus && (
        <div className="sb-analysis-progress">
          {PROGRESS_STEPS.map(({ step, label }) => {
            const done = analysisStatus.step > step;
            const active = analysisStatus.step === step;
            return (
              <div key={step} className={`sb-progress-step ${done ? "done" : active ? "active" : ""}`}>
                <span className="sb-progress-icon">{done ? "✅" : active ? "⏳" : "○"}</span>
                <span className="sb-progress-label">{label}</span>
              </div>
            );
          })}
        </div>
      )}

      {error && <div className="sb-practice-error">{error}</div>}

      {result && (
        <div className="sb-practice-result">
          <ResultViewer data={result} />
        </div>
      )}
    </div>
  );
}

// ─── Lab Page ─────────────────────────────────────────────────────
function Lab() {
  const { user } = useAuth();

  const [analysis, setAnalysis] = useState(null);
  const [analysisLoading, setAnalysisLoading] = useState(false);

  const [sentences, setSentences] = useState([]);
  const [sentencesLoading, setSentencesLoading] = useState(false);
  const [practiceStarted, setPracticeStarted] = useState(false);

  // ─── 페이지 진입 시 자동 분석 로드 ─────────────────────────────
  useEffect(() => {
    if (!user) return;
    setAnalysisLoading(true);
    fetchHistory(1)
      .then(async (history) => {
        const latest = history[0];
        if (!latest) return;
        const { data } = await api.post("/api/lab/feedback", {
          current_session_id: latest.id,
        });
        setAnalysis(data);
      })
      .catch(() => {})
      .finally(() => setAnalysisLoading(false));
  }, [user]);

  // ─── Start Practice: 연습 문장 생성 ────────────────────────────
  const handleStartPractice = async () => {
    if (!analysis) return;
    setPracticeStarted(true);
    setSentencesLoading(true);
    try {
      const { data } = await api.post("/api/lab/sentences", {
        feedback: analysis.feedback,
      });
      const generated = data.sentences || [];
      setSentences(generated);
      // 각 문장 사전 캐싱 (분석 전 워밍)
      generated.forEach((s) => prepareAnalysis(s).catch(() => {}));
    } catch {
      setSentences([]);
    } finally {
      setSentencesLoading(false);
    }
  };

  if (!user) {
    return (
      <div className="sb-lab">
        <div className="sb-lab-icon">🧪</div>
        <div className="sb-lab-title">Practice Lab</div>
        <div className="sb-lab-sub">Please sign in to view your personalized practice.</div>
      </div>
    );
  }

  return (
    <div className="sb-lab-page">

      {/* ── Header ── */}
      <div className="sb-lab-header">
        <div className="sb-lab-title">🧪 Practice Lab</div>
        <div className="sb-lab-sub">
          Targeted practice based on your pronunciation patterns
        </div>
      </div>

      {/* ── Pattern Analysis Card ── */}
      <div className="sb-lab-card">
        <div className="sb-lab-card-label">📊 Pattern Analysis</div>

        {analysisLoading && (
          <div className="sb-lab-loading">
            <div className="sb-spinner" />
            Analyzing your history…
          </div>
        )}

        {!analysisLoading && !analysis && (
          <div className="sb-lab-empty">
            No sessions yet. Complete a session in Pronunciation Coach first.
          </div>
        )}

        {!analysisLoading && analysis && (
          <>
            <div className="sb-lab-analysis-text">{analysis.feedback}</div>
            {analysis.retrieved_count > 0 && (
              <div className="sb-lab-analysis-meta">
                Based on {analysis.retrieved_count} similar past sessions
              </div>
            )}
            {!practiceStarted && (
              <div className="sb-lab-action-row">
                <button
                  className="sb-btn sb-btn-primary sb-btn-lg"
                  onClick={handleStartPractice}
                >
                  🎯 Start Practice
                </button>
              </div>
            )}
          </>
        )}
      </div>

      {/* ── Practice Section ── */}
      {practiceStarted && (
        <div className="sb-practice-section">
          {sentencesLoading && (
            <div className="sb-lab-loading" style={{ justifyContent: "center", padding: "32px 0" }}>
              <div className="sb-spinner" />
              Generating practice sentences…
            </div>
          )}

          {!sentencesLoading && sentences.length === 0 && (
            <div className="sb-lab-empty" style={{ textAlign: "center", padding: "32px 0" }}>
              Failed to generate sentences. Please try again.
            </div>
          )}

          {!sentencesLoading && sentences.map((sentence, i) => (
            <PracticeCard
              key={i}
              index={i}
              sentence={sentence}
              user={user}
            />
          ))}
        </div>
      )}

    </div>
  );
}

export default Lab;
