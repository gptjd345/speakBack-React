import React, { useState } from "react";
import { useAuth } from "../contexts/AuthContext";
import useLangGraph from "../hooks/useLangGraph";
import AudioUploader from "../components/AudioUploader";
import TargetTextInput from "../components/TargetTextInput";
import ResultViewer from "../components/ResultViewer";
import Toast from "../components/Toast";
import "../styles/Coach.css";

// ─── History Panel ────────────────────────────────────────────────────────────
function HistoryPanel({ history, selected, onSelect }) {
  return (
    <aside className="sb-coach-history">
      <div className="sb-history-title">Session History</div>
      <div className="sb-history-sub">Your recent practice sessions</div>

      {history.length === 0 ? (
        <div className="sb-history-empty">
          <div className="sb-history-empty-icon">🕐</div>
          <div>No sessions yet.</div>
          <div style={{ marginTop: "4px" }}>
            Complete your first analysis to see history here.
          </div>
        </div>
      ) : (
        history.map((item, i) => (
          <div
            key={i}
            className={`sb-history-item ${selected === i ? "selected" : ""}`}
            onClick={() => onSelect(i)}
          >
            <div className="sb-history-item-top">
              <div className="sb-history-text">{item.target_text}</div>
              <div className="sb-history-score">{item.score}</div>
            </div>
            <div className="sb-history-date">{item.date}</div>
          </div>
        ))
      )}
    </aside>
  );
}

// ─── Coach Page ───────────────────────────────────────────────────────────────
function Coach() {
  const { user } = useAuth();
  const { loading, runLangGraphProcess } = useLangGraph();

  const [targetText, setTargetText]       = useState("");
  const [file, setFile]                   = useState(null);
  const [history, setHistory]             = useState([]);
  const [selectedHistory, setSelectedHistory] = useState(null);
  const [activeResult, setActiveResult]   = useState(null); // 방금 분석한 결과
  const [toast, setToast]                 = useState({ show: false, message: "" });

  const showToast = (message) => {
    setToast({ show: true, message });
    setTimeout(() => setToast({ show: false, message: "" }), 3000);
  };

  const handleSend = async () => {
    if (!user)              { showToast("Please sign in to use the Pronunciation Coach."); return; }
    if (!file)              { showToast("Please upload or record an audio file."); return; }
    if (!targetText.trim()) { showToast("Please enter a target sentence."); return; }

    setActiveResult(null);
    setSelectedHistory(null);

    const res = await runLangGraphProcess(file, user, targetText);
    if (res) {
      const dated = {
        ...res,
        date: new Date().toLocaleDateString("en-US", {
          month: "short", day: "numeric",
          hour: "2-digit", minute: "2-digit",
        }),
      };
      setActiveResult(dated);
      setHistory((prev) => [dated, ...prev]);
    }
  };

  // History 항목 클릭 시 해당 결과 표시
  const handleHistorySelect = (i) => {
    setSelectedHistory(i);
    setActiveResult(null);
  };

  const displayResult =
    selectedHistory !== null ? history[selectedHistory] : activeResult;

  return (
    <div className="sb-coach-layout">
      <Toast message={toast.message} show={toast.show} />

      {/* ── Left: Input + Result ── */}
      <div className="sb-coach-main">
        <div className="sb-section-header">
          <div className="sb-section-title">Pronunciation Coach</div>
          <div className="sb-section-sub">
            Record or upload your voice and get instant AI feedback
          </div>
        </div>

        {/* Target Sentence */}
        <div className="sb-card">
          <div className="sb-card-label">📝 Target Sentence</div>
          <TargetTextInput value={targetText} onChange={setTargetText} />
        </div>

        {/* Audio */}
        <div className="sb-card">
          <div className="sb-card-label">🎤 Your Voice</div>
          <AudioUploader file={file} setFile={setFile} />
        </div>

        {/* Send Row */}
        <div className="sb-send-row">
          <button
            className="sb-btn sb-btn-primary sb-btn-lg"
            onClick={handleSend}
            disabled={loading}
          >
            {loading ? (
              <>
                <span className="sb-spinner" style={{ borderTopColor: "white" }} />
                Analyzing…
              </>
            ) : (
              "✨ Analyze Pronunciation"
            )}
          </button>
        </div>

        {/* Result */}
        {displayResult && (
          <div className="sb-results">
            <ResultViewer data={displayResult} />
          </div>
        )}
      </div>

      {/* ── Right: History ── */}
      <HistoryPanel
        history={history}
        selected={selectedHistory}
        onSelect={handleHistorySelect}
      />
    </div>
  );
}

export default Coach;
