import { useState } from "react";
import { runLangGraphRequestStream } from "../api/langgraphApi";

export default function useLangGraph() {
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");
  const [analysisStatus, setAnalysisStatus] = useState(null); // { step, total, status }

  const runLangGraphProcess = async (file, user, targetText) => {
    if (!file) {
      setError("No audio file selected.");
      return;
    }

    setLoading(true);
    setError("");
    setResult(null);
    setAnalysisStatus(null);

    try {
      let finalResult = null;

      await runLangGraphRequestStream(
        file,
        user,
        targetText,
        (progress) => setAnalysisStatus(progress),
        (res) => { finalResult = res; },
      );

      setResult(finalResult);
      return finalResult;
    } catch (err) {
      setError(err.message || "Unknown error occurred");
    } finally {
      setLoading(false);
      setAnalysisStatus(null);
    }
  };

  return { loading, result, error, analysisStatus, runLangGraphProcess };
}
