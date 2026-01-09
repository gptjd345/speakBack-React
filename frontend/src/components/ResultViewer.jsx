// src/components/ResultViewer.jsx
import React from "react";

export default function ResultViewer({ data }) {
  if (!data) return null;

  // undefined 대비
  const strengths = data.strengths ?? [];
  const improvements = data.improvements ?? [];
  const rhythm = data.rhythm_feedback ?? "";

  return (
    <div className="result-viewer">
      <h3>Results for {data.user_name}</h3>
      <p>Target Text: {data.target_text}</p>

      <div>
        <h4>US Tutor Feedback:</h4>
        <h4>What you did well</h4>
        <ul>
          {strengths.map((w, i) => <li key={i}>✅ {w}</li>)}
        </ul>

        <h4>Needs improvement</h4>
        <ul>
          {improvements.map((w, i) => <li key={i}>⚠️ {w}</li>)}
        </ul>

        <h4>Rhythm & Speed</h4>
        <p>{rhythm}</p>
        {data.us_audio && <audio controls src={`data:audio/wav;base64,${data.us_audio}`} />}
      </div>

      {/* 추후 개발 예정
        <div>
          <h4>UK Tutor Feedback:</h4>
          <p>{data.uk_feedback}</p>
          {data.uk_audio && <audio controls src={`data:audio/wav;base64,${data.uk_audio}`} />}
        </div>
      */}
        <p>Score: {data.score}</p>
      
    </div>
    
  );
}
