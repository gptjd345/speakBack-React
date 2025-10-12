import React from "react";
import "../styles/Header.css";

function Header({ isLoggedIn, onLoginClick }) {
  return (
    <header className="header">
      <div className="logo">SpeakBack</div>
      {!isLoggedIn && (
        <button className="login-btn" onClick={onLoginClick}>
          Login
        </button>
      )}
    </header>
  );
}

export default Header;
