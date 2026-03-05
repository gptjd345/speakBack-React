// api.js
import axios from "axios";

const IS_PROD = process.env.REACT_APP_ENV === "production";

const api = axios.create({
  baseURL: process.env.REACT_APP_API_BASE_URL,
  withCredentials: IS_PROD, // 운영: 쿠키 전송 / 로컬: 불필요
});

// 로컬 개발: localStorage에서 토큰 꺼내서 헤더에 담음
// 운영: 쿠키를 브라우저가 자동으로 담아주므로 인터셉터 불필요
if (!IS_PROD) {
  api.interceptors.request.use((config) => {
    const access_token = localStorage.getItem("access_token");
    const refresh_token = localStorage.getItem("refresh_token");
    if (access_token) {
      config.headers["Authorization"] = `Bearer ${access_token}`;
    }
    if (refresh_token) {
      config.headers["X-Refresh-Token"] = refresh_token;
    }
    return config;
  });
}

export default api;
