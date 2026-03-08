import React, { useState, useEffect } from "react";
import { useAuth } from "../contexts/AuthContext";
import useLangGraph from "../hooks/useLangGraph";
import AudioUploader from "../components/AudioUploader";
import TargetTextInput from "../components/TargetTextInput";
import ResultViewer from "../components/ResultViewer";
import Toast from "../components/Toast";
import { fetchHistory, fetchHistoryDetail } from "../api/langgraphApi";
import "../styles/Coach.css";

// ─── 날짜 포맷 헬퍼 ──────────────────────────────────────────────
function formatDate(isoString) {
  const d = new Date(isoString);
  return d.toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

// ─── History Panel ────────────────────────────────────────────────────────────
function HistoryPanel({ history, selectedId, onSelect, loading }) {
  return (
    <aside className="sb-coach-history">
      <div className="sb-history-title">Session History</div>
      <div className="sb-history-sub">Your recent practice sessions</div>

      {loading && (
        <div className="sb-history-empty">
          <div className="sb-spinner" style={{ margin: "0 auto" }} />
        </div>
      )}

      {!loading && history.length === 0 && (
        <div className="sb-history-empty">
          <div className="sb-history-empty-icon">🕐</div>
          <div>No sessions yet.</div>
          <div style={{ marginTop: "4px" }}>
            Complete your first analysis to see history here.
          </div>
        </div>
      )}

      {!loading &&
        history.map((item) => (
          <div
            key={item.id}
            className={`sb-history-item ${selectedId === item.id ? "selected" : ""}`}
            onClick={() => onSelect(item.id)}
          >
            <div className="sb-history-item-top">
              <div className="sb-history-text">{item.target_text}</div>
              <div className="sb-history-score">{item.score ?? "-"}</div>
            </div>
            <div className="sb-history-date">{formatDate(item.created_at)}</div>
          </div>
        ))}
    </aside>
  );
}

// ─── Coach Page ───────────────────────────────────────────────────────────────
function Coach() {
  const { user } = useAuth();
  const { loading: analyzing, runLangGraphProcess } = useLangGraph();

  const [targetText, setTargetText]       = useState("");
  const [file, setFile]                   = useState(null);

  // 방금 분석한 결과
  const [activeResult, setActiveResult] = useState(null);  

  // 히스토리 목록
  const [history, setHistory]             = useState([]);
  const [historyLoading, setHistoryLoading] = useState(false);

  // 히스토리에서 선택한 상세 결과
  const [selectedId, setSelectedId] = useState(null);
  const [detailLoading, setDetailLoading] = useState(false);
  
  const [toast, setToast] = useState({ show: false, message: "" });

  // ─── 히스토리 목록 로드 ─────────────────────────────────────────
  const loadHistory = async () => {
    if (!user) return;
    setHistoryLoading(true);
    try {
      const data = await fetchHistory(20);
      setHistory(data);
    } catch {
      // 로그인 안 된 상태 등 조용히 무시
    } finally {
      setHistoryLoading(false);
    }
  };

  useEffect(() => {
    loadHistory();
  }, [user]);

  // ─── 히스토리 항목 클릭 → 상세 조회 ────────────────────────────
  const handleHistorySelect = async (id) => {
    if (selectedId === id) return; // 같은 항목 재클릭 무시
    setSelectedId(id);
    setActiveResult(null);
    setDetailLoading(true);
    try {
      const detail = await fetchHistoryDetail(id);
      setActiveResult(detail);
    } catch {
      showToast("Failed to load session detail.");
    } finally {
      setDetailLoading(false);
    }
  };

  const showToast = (message) => {
    setToast({ show: true, message });
    setTimeout(() => setToast({ show: false, message: "" }), 3000);
  };

  const handleSend = async () => {
    if (!user)              { showToast("Please sign in to use the Pronunciation Coach."); return; }
    if (!file)              { showToast("Please upload or record an audio file."); return; }
    if (!targetText.trim()) { showToast("Please enter a target sentence."); return; }

    setActiveResult(null);
    setSelectedId(null);

    const res = await runLangGraphProcess(file, user, targetText);
    console.log("########## res:", res);  
    if (res) {
      setActiveResult(res);
      // 분석 완료 후 히스토리 목록 갱신
      await loadHistory();
    }
  };

  const displayResult = activeResult;

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
            disabled={analyzing}
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

        {/* 히스토리 상세 로딩 */}
        {detailLoading && (
          <div className="sb-loading">
            <div className="sb-spinner" />
            Loading session…
          </div>
        )}

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
        selectedId={selectedId}
        onSelect={handleHistorySelect}
        loading={historyLoading}
      />
    </div>
  );
}

export default Coach;
