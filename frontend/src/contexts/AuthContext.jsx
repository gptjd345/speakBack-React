// src/contexts/AuthContext.jsx
import React, { createContext, useState, useEffect, useContext } from "react";
import api from "../utils/api";

export const AuthContext = createContext();

export const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(null); // 로그인한 사용자 정보
  const [loading, setLoading] = useState(true);

  // 앱 첫 로드 시 1회만 /api/me 호출
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

  // 로그인/로그아웃 후에도 상태를 갱신할 수 있도록 helper 제공
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

  // 로그인 데이터를 전역으로 저장
  const login = (userData) => {
    if(!userData) return;

    setUser(userData);
    console.log("user->", userData);

  };

  const logout = async () => {
    await api.post("/api/auth/logout");
    setUser(null);
    // 로컬스토리지/세션스토리지에서 토큰 제거
    localStorage.removeItem("access_key");
  };

  return (
    <AuthContext.Provider value={{ user, setUser, refreshUser, login, logout, loading }}>
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => useContext(AuthContext);