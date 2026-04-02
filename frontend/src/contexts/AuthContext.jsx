import { createContext, useState, useEffect, useContext } from "react";
import api from "../utils/api";

export const AuthContext = createContext();

export const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  const fetchMe = async () => {
    const res = await api.post("/api/auth/me");
    if (res.data.user) {
      setUser(res.data.user);
    }
  }

  // 앱 첫 로드 시 세션 확인
  // access token 없으면 비로그인 상태로 바로 종료
  // access token 만료 시 refresh 시도 (쿠키의 refresh token 자동 전송)
  useEffect(() => {
    const initAuth = async () => {
      if (!localStorage.getItem("access_token")) {
        setLoading(false);
        return;
      }

      try {
        await fetchMe();
      } catch (err) {
        if (err.response?.status === 401) {
          try {
            const refreshRes = await api.post("/api/auth/refresh");
            localStorage.setItem("access_token", refreshRes.data.access_token);
            await fetchMe();
          } catch {
            setUser(null);
            localStorage.removeItem("access_token");
          }
        } else {
          setUser(null);
        }
      } finally {
        setLoading(false);
      }
    };

    initAuth();
  }, []);

  const login = (userData) => {
    if (!userData) return;
    setUser(userData);
  };

  const logout = async () => {
    try {
      await api.post("/api/auth/logout");
    } catch {
      // 로그아웃 실패해도 클라이언트 상태는 초기화
    }
    setUser(null);
    localStorage.removeItem("access_token");
  };

  const refreshUser = async () => {
    try {
      await fetchMe();
    } catch {
      setUser(null);
    }
  };

  return (
    <AuthContext.Provider value={{ user, setUser, refreshUser, login, logout, loading }}>
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => useContext(AuthContext);
