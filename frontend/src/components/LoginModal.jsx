import { useState } from "react";
import { useAuth } from "../contexts/AuthContext";
import api from "../utils/api";
import "../styles/LoginModal.css";

function LoginModal({ onClose }) {
  const { login } = useAuth();
  const [tab, setTab] = useState("login");
  const [form, setForm] = useState({ username: "", password: "", email: "" });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const update = (key) => (e) =>
    setForm((prev) => ({ ...prev, [key]: e.target.value }));

  const performLogin = async (username, password) => {
    const res = await api.post("/api/auth/login", { username, password });
    
    localStorage.setItem("access_token", res.data.access_token);

    return res.data.user;
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError("");
  
    try {
      if (tab === "register") {
        // FastAPI 백엔드로 회원가입 요청
        await api.post("/api/auth/register", {
          username: form.username,
          password: form.password,
          email: form.email,
        });
        alert("Registration successful!");
      }
      // 회원가입 후 바로 로그인
      const user = await performLogin(form.username, form.password);
      login(user);
      onClose();
    } catch (error) {
      const msg = error.response?.data?.detail || error.message || "Something went wrong.";
      setError(msg);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div
      className="sb-modal-overlay"
      onMouseDown={(e) => { if (e.target === e.currentTarget) onClose(); }}
    >
      <div className="sb-modal">
        <button className="sb-modal-close-btn" onClick={onClose}>X</button>

        <div className="sb-modal-title">
          {tab === "login" ? "Welcome back" : "Create account"}
        </div>
        <div className="sb-modal-sub">
          {tab === "login"
            ? "Sign in to track your progress."
            : "Join SpeakBack and start improving."}
        </div>

        {/* Tabs */}
        <div className="sb-modal-tabs">
          <button
            className={`sb-modal-tab ${tab === "login" ? "active" : ""}`}
            onClick={() => setTab("login")}
          >
            Login
          </button>
          <button
            className={`sb-modal-tab ${tab === "register" ? "active" : ""}`}
            onClick={() => setTab("register")}
          >
            Register
          </button>
        </div>

        <form onSubmit={handleSubmit}>
          <input
            className="sb-input"
            placeholder="Username"
            value={form.username}
            onChange={update("username")}
            required
          />
          <input
            className="sb-input"
            type="password"
            placeholder="Password"
            value={form.password}
            onChange={update("password")}
            required
          />
          {tab === "register" && (
            <input
              className="sb-input"
              type="email"
              placeholder="Email"
              value={form.email}
              onChange={update("email")}
              required
            />
          )}

          {error && <div className="sb-modal-error">{error}</div>}

          <button
            type="submit"
            className="sb-btn sb-btn-primary sb-modal-submit"
            disabled={loading}
          >
            {loading
              ? "Please wait…"
              : tab === "login"
              ? "Sign in"
              : "Create account"}
          </button>
        </form>
      </div>
    </div>
  );
}

export default LoginModal;
