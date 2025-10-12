import React, { useState } from "react";
import "../styles/LoginModal.css";

function LoginModal({ onClose, onLogin }) {
  const [option, setOption] = useState("Login");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [email, setEmail] = useState("");

  const handleSubmit = (e) => {
    e.preventDefault();
    alert(`${option} submitted!`);
    onLogin();
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
