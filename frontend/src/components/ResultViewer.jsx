// src/components/ResultViewer.jsx
import React from "react";
import "../styles/ResultViewer.css";

function ResultViewer({ data }) {
  if (!data) return null;

  // undefined 대비
  const strengths = data.strengths ?? [];
  const improvements = data.improvements ?? [];
  const rhythm = data.rhythm_feedback ?? "";

  return (
    <div className="sb-result-card">
      {/* Header with score */}
      <div className="sb-result-header">
        <div className="sb-result-score-row">
          <div>
            <div className="sb-result-label">Results for</div>
            <div className="sb-result-name">{data.user_name}</div>
          </div>
          <div className="sb-score-ring">
            <div className="sb-score-num">{data.score}</div>
            <div className="sb-score-sub">/ 100</div>
          </div>
        </div>
        <div className="sb-result-target">"Target Text: {data.target_text}"</div>
      </div>

      {/* Body */}
      <div className="sb-result-body">
        {/* Strengths */}
        <div className="sb-result-section">
          <div className="sb-result-section-title good">✅ What you did well</div>
          <ul className="sb-result-list">
            {strengths.map((s, i) => (
              <li key={i}><span>•</span>{s}</li>
            ))}
          </ul>
        </div>

        {/* Improvements */}
        <div className="sb-result-section">
          <div className="sb-result-section-title warn">⚠️ Needs improvement</div>
          <ul className="sb-result-list">
            {improvements.map((s, i) => (
              <li key={i}><span>•</span>{s}</li>
            ))}
          </ul>
        </div>

        {/* Rhythm */}
        <div className="sb-result-section">
          <div className="sb-result-section-title info">🎵 Rhythm & Speed</div>
          <div className="sb-rhythm-box">{rhythm}</div>
        </div>

        {/* Audio playback */}
        {data.us_audio && (
          <audio
            className="sb-result-audio"
            controls
            src={`data:audio/wav;base64,${data.us_audio}`}
          />
        )}
      
      {/* 추후 개발 예정
        <div>
          <h4>UK Tutor Feedback:</h4>
          <p>{data.uk_feedback}</p>
          {data.uk_audio && <audio controls src={`data:audio/wav;base64,${data.uk_audio}`} />}
        </div>
      */}
      </div> 
    </div>
  );
}

export default ResultViewer;