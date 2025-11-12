// api.js
import axios from "axios";

console.log("API Base URL:", process.env.REACT_APP_API_BASE_URL);
const api = axios.create({
  baseURL: process.env.REACT_APP_API_BASE_URL, // 환경변수 사용
  //withCredentials: true, 쿠키 일단 안쓰므로
  withCredentials: false,
});

// 로컬 테스트용: 요청 전마다 access_key를 로컬스토리지에서 붙임
api.interceptors.request.use((config) => {
  const access_key = localStorage.getItem("access_key"); // 테스트용
  if (access_key) {
    config.headers["X-Access-Key"] = access_key; // 커스텀 헤더로 전송
  }
  return config;
});

export default api;
