import { useState } from "react";
import { runLangGraphRequest } from "../api/langgraphApi";

export default function useLangGraph() {
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");

  const runLangGraphProcess = async (file, user, targetText) => {
    if (!file) {
      setError("No audio file selected.");
      return;
    }

    setLoading(true);
    setError("");
    setResult(null);

    try {
      const response = await runLangGraphRequest(file, user, targetText);
      setResult(response);
    } catch (err) {
      setError(err.message || "Unknown error occurred");
    } finally {
      setLoading(false);
    }
  };

  return { loading, result, error, runLangGraphProcess };
}
