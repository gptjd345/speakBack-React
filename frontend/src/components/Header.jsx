import React from "react";
import { useAuth } from "../contexts/AuthContext";
import "../styles/Header.css";

const PAGE_TITLES = {
  home:  "SpeakBack",
  coach: "Pronunciation Coach",
  lab:   "Practice Lab",
};

function Header({ page, onLoginClick, onLogoutClick }) {
  const { user } = useAuth();
  return (
    <header className="sb-header">
      <div className="sb-header-title">{PAGE_TITLES[page] || "SpeakBack"}</div>
      <div className="sb-header-actions">
        {!user && (
          <button className="sb-btn sb-btn-primary" onClick={onLoginClick}>
            Sign in
          </button>
        )}
      </div>
    </header>
  );
}

export default Header;
