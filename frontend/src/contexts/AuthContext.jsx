import React, { createContext, useState, useEffect, useContext } from "react";
import api from "../utils/api";
const IS_PROD = process.env.REACT_APP_ENV === "production";

export const AuthContext = createContext();

export const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  // me 요청 에러 핸들링은 호출자가 한다.
  const fetchMe = async () => {
    const res = await api.post("/api/auth/me");
    if (res.data.user) {
      setUser(res.data.user);
      console.log("fetchMe response:", res.data);
    }
  }

  // 앱 첫 로드 시 세션 확인
  // /me 요청 실패 시(access token 만료) -> refresh 요청 -> 성공하면 새 access 토큰으로 재시도
  useEffect(() => {
    const initAuth = async () => {
    // 로컬: 토큰 없으면 비로그인 상태로 바로 종료
    if (!IS_PROD && !localStorage.getItem("access_token")) {
      setLoading(false);
      return;
    }

      try {
        await fetchMe();

      } catch (err){
        // access token 만료 or 없음 -> refresh 시도
        if(err.response?.status === 401){
          try {
            const refreshRes = await api.post("/api/auth/refresh"); // refresh 토큰으로 access 토큰 발급

            // 새 토큰 localStorage 업데이트
            if (!IS_PROD) {
              localStorage.setItem("access_token", refreshRes.data.access_token);
              localStorage.setItem("refresh_token", refreshRes.data.refresh_token);
            }

            await fetchMe(); // 새 access 토큰으로 재시도
          } catch {
            setUser(null); // refresh도 만료된 경우 로그인 필요
          }
        } else {
          setUser(null); // 로그인 안 된 상태
        }
        
      } finally {
        setLoading(false);
      }
    };

    initAuth();
  }, []);

  // 로그인 데이터를 전역으로 저장
  const login = (userData) => {
    if(!userData) return;
    setUser(userData);
  };

  const logout = async () => {
    try {
      await api.post("/api/auth/logout");
    } catch {
      // 로그아웃 실패해도 클라이언트 상태는 초기화
    }
    setUser(null);
    if (!IS_PROD) {
      localStorage.removeItem("access_token");
      localStorage.removeItem("refresh_token");
    }
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