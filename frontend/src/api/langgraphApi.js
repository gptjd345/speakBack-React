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

/**
 * SSE 스트리밍 분석
 * onProgress({ step, total, status }): 진행 단계 콜백
 * onResult(result): 최종 결과 콜백
 */
export async function runLangGraphRequestStream(file, user, targetText, onProgress, onResult) {
  // Step 1: Presigned URL 발급
  const { data: { upload_url, s3_key } } = await api.post("/api/analyze/upload-url", {
    filename: file.name || "audio.wav",
    content_type: file.type || "audio/wav",
  });

  // Step 2: S3 직접 업로드
  await fetch(upload_url, {
    method: "PUT",
    headers: { "Content-Type": file.type || "audio/wav" },
    body: file,
  });

  // Step 3: SSE 스트리밍 분석
  const formData = new FormData();
  formData.append("s3_key", s3_key);
  formData.append("user_name", user?.username || "");
  formData.append("target_text", targetText);
  formData.append("original_filename", file.name || "audio.wav");

  const token = localStorage.getItem("access_token");
  const baseURL = process.env.REACT_APP_API_BASE_URL || "";

  const response = await fetch(`${baseURL}/api/analyze/process/stream`, {
    method: "POST",
    headers: token ? { Authorization: `Bearer ${token}` } : {},
    body: formData,
  });

  if (!response.ok) throw new Error("분석 요청 실패");

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split("\n");
    buffer = lines.pop(); // 마지막 불완전한 라인은 버퍼에 유지

    for (const line of lines) {
      if (!line.startsWith("data: ")) continue;
      const data = JSON.parse(line.slice(6));
      if (data.error) throw new Error(data.error);
      if (data.done) onResult(data.result);
      else onProgress(data);
    }
  }
}

// ─── 문장 제안 (tone 감지 + 문법 교정 + formal/neutral/informal 변환) ─
export async function fetchSuggestions(targetText) {
  const response = await api.post("/api/analyze/suggest", { target_text: targetText });
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
