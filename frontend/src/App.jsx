import React, { useState } from "react";
import { AuthProvider } from "./contexts/AuthContext";

import Sidebar     from "./components/Sidebar";
import Header      from "./components/Header";
import LoginModal from "./components/LoginModal";

import Home  from "./pages/Home";
import Coach from "./pages/Coach";
import Lab   from "./pages/Lab";

import "./styles/global.css";

function AppContent() {
  const [page, setPage]           = useState("home");
  const [showLogin, setShowLogin] = useState(false);

  const renderPage = () => {
    switch (page) {
      case "coach": return <Coach />;
      case "lab":   return <Lab />;
      default:      return <Home onNavigate={setPage} onLoginClick={() => setShowLogin(true)} />;
    }
  };

  return (
    <div className="sb-root">
      <Sidebar active={page} onNavigate={setPage} />

      <div className="sb-main">
        <Header page={page} onLoginClick={() => setShowLogin(true)} />
        <div className="sb-content">
          {renderPage()}
        </div>
      </div>

      {showLogin && <LoginModal onClose={() => setShowLogin(false)} />}
    </div>
  );
}

// App 전체를 AuthProvider로 감싸서 전역 상태 제공
function App() {
  return (
    <AuthProvider>
      <AppContent />
    </AuthProvider>
  );
}

export default App;
