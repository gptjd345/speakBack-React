import React from "react";
import "../styles/Header.css";

function Header({ isLoggedIn, onLoginClick, onLogoutClick }) {
  console.log("Header - isLoggedIn:", isLoggedIn); // 로그인 상태 확인용
  return (
    <header className="header">
      <div className="logo">SpeakBack</div>
      <div>
        {isLoggedIn ? (
          <button className="login-btn" onClick={onLogoutClick}>
            Logout
          </button>
        ) : (
          <button className="login-btn" onClick={onLoginClick}>
            Login
          </button>
        )}
      </div>
    </header>
  );
}

export default Header;
