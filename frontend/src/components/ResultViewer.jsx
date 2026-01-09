// src/components/ResultViewer.jsx
import React from "react";

export default function ResultViewer({ data }) {
  if (!data) return null;

  return (
    <div className="result-viewer">
      <h3>Results for {data.user_name}</h3>
      <p>Target Text: {data.target_text}</p>

      <div>
        <h4>US Tutor Feedback:</h4>
        <p>{data.us_feedback}</p>
        {data.us_audio && <audio controls src={`data:audio/wav;base64,${data.us_audio}`} />}
      </div>

      <div>
        <h4>UK Tutor Feedback:</h4>
        <p>{data.uk_feedback}</p>
        {data.uk_audio && <audio controls src={`data:audio/wav;base64,${data.uk_audio}`} />}
      </div>

      <p>Score: {data.score}</p>
    </div>
  );
}
