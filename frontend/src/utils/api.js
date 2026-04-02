// api.js
import axios from "axios";

const api = axios.create({
  baseURL: process.env.REACT_APP_API_BASE_URL,
  withCredentials: true, // refresh token 쿠키 자동 전송
});

// 인터셉터 없는 별도 인스턴스 — refresh 요청 전용
const authApi = axios.create({
  baseURL: process.env.REACT_APP_API_BASE_URL,
  withCredentials: true,
});

// access token을 Authorization 헤더에 담음
api.interceptors.request.use((config) => {
  const access_token = localStorage.getItem("access_token");
  if (access_token) {
    config.headers["Authorization"] = `Bearer ${access_token}`;
  }
  return config;
});

// 401 시 refresh 시도
api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config;

    const isAuthEndpoint = originalRequest.url?.includes("/api/auth/");
    if (error.response?.status === 401 && !originalRequest._retry && !isAuthEndpoint) {
      originalRequest._retry = true;

      try {
        const refreshRes = await authApi.post("/api/auth/refresh");
        const newAccessToken = refreshRes.data.access_token;

        localStorage.setItem("access_token", newAccessToken);

        originalRequest.headers["Authorization"] = `Bearer ${newAccessToken}`;
        return api(originalRequest);
      } catch {
        localStorage.removeItem("access_token");
        window.location.href = "/";
      }
    }

    return Promise.reject(error);
  }
);

export default api;
