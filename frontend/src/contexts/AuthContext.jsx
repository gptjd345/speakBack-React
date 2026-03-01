import React, { createContext, useState, useEffect, useContext } from "react";
import api from "../utils/api";

export const AuthContext = createContext();

export const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  // 앱 첫 로드 시 세션 확인
  useEffect(() => {
    const fetchUser = async () => {
      try {
        const res = await api.post("/api/auth/me");

        // 로컬 테스트용으로 access_key를 로컬스토리지에 저장
        if(res.data.access_key && res.data.access_key !== "undefined"){
          localStorage.setItem("access_key", res.data.access_key);
          setUser(res.data.user);
          console.log("##### /api/auth/me localStorage 통과여부 : ", res.data.access_key);
        }
      } catch {
        setUser(null); // 로그인 안 된 상태
      } finally {
        setLoading(false);
      }
    };
    fetchUser();
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
    localStorage.removeItem("access_key");
  };

  const refreshUser = async () => {
    try {
        const res = await api.post("/api/auth/me");
        // 로컬 테스트용으로 access_key를 로컬스토리지에 저장
        localStorage.setItem("access_key", res.access_key);
      setUser(res.data.user);
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