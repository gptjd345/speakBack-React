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

  // response 인터셉터 (추가)
  api.interceptors.response.use(
    (response) => response, // 성공은 그대로
    async (error) => {
      const originalRequest = error.config;

      // 401이고 refresh 재시도 안 한 요청만
      if (error.response?.status === 401 && !originalRequest._retry) {
        originalRequest._retry = true; // 무한루프 방지

        try {
          const refreshRes = await api.post("/api/auth/refresh");
          const newAccessToken = refreshRes.data.access_token;
          const newRefreshToken = refreshRes.data.refresh_token;

          localStorage.setItem("access_token", newAccessToken);
          localStorage.setItem("refresh_token", newRefreshToken);

          // 원래 요청 헤더 업데이트 후 재시도
          originalRequest.headers["Authorization"] = `Bearer ${newAccessToken}`;
          return api(originalRequest);
        } catch {
          // refresh도 실패 → 로그아웃 처리
          localStorage.removeItem("access_token");
          localStorage.removeItem("refresh_token");
          window.location.href = "/"; // 로그인 페이지로
        }
      }

      return Promise.reject(error);
    }
  );

}

export default api;
