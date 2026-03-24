import api from "../utils/api"

/**
 * 전체 분석 흐름:
 * 1. FastAPI에서 Presigned Upload URL 발급
 * 2. S3에 직접 PUT 업로드 (FastAPI 거치지 않음)
 * 3. FastAPI에 s3_key 전달해서 분석 실행
 */
export async function runLangGraphRequest(file, user, targetText) {
  // ── Step 1: Presigned URL 발급 ──────────────────────────────
  const { data: { upload_url, s3_key } } = await api.post("/api/analyze/upload-url", {
    filename: file.name || "audio.wav",
    content_type: file.type || "audio/wav",
  });

  // ── Step 2: S3 직접 업로드 (axios 인터셉터 헤더 제외) ───────
  await fetch(upload_url, {
    method: "PUT",
    headers: { "Content-Type": file.type || "audio/wav" },
    body: file,
  });

  // ── Step 3: 분석 실행 ────────────────────────────────────────
  const formData = new FormData();
  formData.append("s3_key", s3_key);
  formData.append("user_name", user?.username || "");
  formData.append("target_text", targetText);
  formData.append("original_filename", file.name || "audio.wav");

  const response = await api.post("/api/analyze/process", formData, {
    headers: { "Content-Type": "multipart/form-data" },
  });

  return response.data;
}

// ─── target text 사전 분석 (캐시 워밍) ───────────────────────────
export async function prepareAnalysis(targetText) {
  await api.post("/api/analyze/prepare", { target_text: targetText });
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
