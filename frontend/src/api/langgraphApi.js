export async function runLangGraphRequest(file, user, targetText) {
  const formData = new FormData();
  formData.append("audio", file);
  formData.append("user_name", user?.username || "");
  formData.append("target_text", targetText);

  const response = await fetch("http://localhost:8000/api/analyze/process", {
    method: "POST",
    body: formData,
  });

  if (!response.ok) {
    const err = await response.json();
    throw new Error(err.detail || "LangGraph request failed");
  }

  return await response.json();
}
