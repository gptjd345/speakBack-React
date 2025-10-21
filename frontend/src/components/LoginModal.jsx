import React, { useState } from "react";
import "../styles/LoginModal.css";

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
        const response = await fetch("http://localhost:8000/register", {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({ username, password, email }),
        });

        if (!response.ok) {
          const errorData = await response.json();
          alert(`Error: ${errorData.detail}`);
        } else {
          alert("Registration successful!");
          onLogin(); // 로그인 후 처리
        }
      } else {
        // 로그인 로직
        const response = await fetch("http://localhost:8000/login", {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({ username, password }),
        });

        if (!response.ok) {
          const errorData = await response.json();
          alert(`Error: ${errorData.detail}`);
        } else {
          const data = await response.json();
          alert("Login successful!");
          // JWT 처리나 상태 관리
          onLogin(data);
        }
      }
    } catch (error) {
      console.error(error);
      alert("Something went wrong!");
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
