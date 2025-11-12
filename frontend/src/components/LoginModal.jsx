import React, { useState } from "react";
import "../styles/LoginModal.css";
import api from "../utils/api";

function LoginModal({ onClose, onLogin }) {
  const [option, setOption] = useState("Login");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [email, setEmail] = useState("");

  const handleSubmit = async (e) => {
    e.preventDefault();
    alert(`${option} submitted!`);
    try {
      if (option === "Register") {
        // FastAPI 백엔드로 회원가입 요청
        const response = await api.post("/api/auth/register", {
          username,
          password,
          email,
        });
        alert("Registration successful!");

        // 회원가입 후 바로 로그인
        const data = await performLogin(username, password);
        onLogin(data);
      } else {
          const data = await performLogin(username, password);
          alert("Login successful!");
          onLogin(data);
        }
      
    } catch (error) {
      console.error(error);
      alert("Something went wrong!");
    }
  };

  // perform login
  const performLogin = async (username, password) => {
  try {
    const res = await api.post("/api/auth/login", { username, password });
    console.log("##### performLogin : ", res.data.access_key);
    console.log("###", res.data.access_key, typeof res.data.access_key);
    if(res.data.access_key && res.data.access_key !== "undefined"){
      // 로컬 테스트용으로 access_key를 로컬스토리지에 저장
      localStorage.setItem("access_key", res.data.access_key);
      console.log("##### performLogin 조건통과여부 : ", res.data.access_key);
    }
    console.log("##### localStorage : ", localStorage.getItem("access_key"));

    // response.data 안에 서버 리턴 데이터가 들어있음
    return res.data.user;
  } catch (err) {
    // 서버가 리턴한 에러 메시지 가져오기
    if (err.response && err.response.data && err.response.data.detail) {
      throw new Error(err.response.data.detail);
    } else {
      throw new Error("Login failed");
    }
  }
  };
  

  return (
    <div className="modal-overlay">
      <div className="modal">
        <button className="close-btn" onClick={onClose}>X</button>
        <h2>{option}</h2>
        <form onSubmit={handleSubmit}>
          <div>
            <label>
              <input 
                type="radio" 
                value="Login" 
                checked={option === "Login"} 
                onChange={() => setOption("Login")} 
              /> Login
            </label>
            <label>
              <input 
                type="radio" 
                value="Register" 
                checked={option === "Register"} 
                onChange={() => setOption("Register")} 
              /> Register
            </label>
          </div>
          <input 
            type="text" 
            placeholder="Username" 
            value={username} 
            onChange={(e) => setUsername(e.target.value)} 
            required 
          />
          <input 
            type="password" 
            placeholder="Password" 
            value={password} 
            onChange={(e) => setPassword(e.target.value)} 
            required 
          />
          {option === "Register" && (
            <input 
              type="email" 
              placeholder="Email" 
              value={email} 
              onChange={(e) => setEmail(e.target.value)} 
              required 
            />
          )}
          <button type="submit">{option}</button>
        </form>
      </div>
    </div>
  );
}

export default LoginModal;
