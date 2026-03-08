import api from "../utils/api"

export async function runLangGraphRequest(file, user, targetText) {
  const formData = new FormData();
  formData.append("audio", file);
  formData.append("user_name", user?.username || "");
  formData.append("target_text", targetText);

  const response = await api.post("/api/analyze/process", formData, {
    headers: { "Content-Type": "multipart/form-data" },
  });

  return response.data;
}

// ─── 히스토리 목록 조회 ───────────────────────────────────────────
export async function fetchHistory(limit = 20) {
  const response = await api.get(`/api/history/?limit=${limit}`);
  return response.data;
}

// ─── 히스토리 단건 상세 조회 ─────────────────────────────────────
export async function fetchHistoryDetail(sessionId) {
  const response = await api.get(`/api/history/${sessionId}`);
  return response.data;
}
