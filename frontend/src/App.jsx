import React, { useState, useEffect } from "react";
import Header from "./components/Header";
import AudioUploader from "./components/AudioUploader";
import LoginModal from "./components/LoginModal";
import TargetTextInput from "./components/TargetTextInput";
import { AuthProvider } from "./contexts/AuthContext";
import { useAuth } from "./contexts/AuthContext";
import Home from "./pages/Home";
import "./styles/App.css";
import "./styles/Header.css";


function AppContent() {
  const { user, login, logout } = useAuth(); // 전역 로그인 상태 사용
  const [showModal, setShowModal] = useState(false);
  const [targetText, setTargetText] = useState("");
  const [showLoginWarning, setShowLoginWarning] = useState(false);

  const handleSendClick = () => {
    if(!user) {
      setShowLoginWarning(true);
    } else {
      setShowLoginWarning(false);
      // 실제 LangGraph 처리
    }
  }

  // 경고창 자동 사라지게
  useEffect(() => {
    if (showLoginWarning) {
      const timer = setTimeout(() => setShowLoginWarning(false), 3000);
      return () => clearTimeout(timer);
    }
  }, [showLoginWarning]);

  console.log("App - user:", user); // 로그인 상태 확인용
  return (
    <div className="App">
      <Header 
        isLoggedIn={!!user} 
        onLoginClick={() => setShowModal(true)}
        onLogoutClick={logout}  // 로그아웃 버튼 클릭 시 실행 
      />

      {/* Toast 형태 경고창 */}
      <div className={`login-warning ${showLoginWarning ? "show" : "hidden"}`}>
        Please login to access the pronunciation coach.
      </div>
      
      <div className="main-content">
        <h1>Pronunciation Coach 🎤</h1>
        <TargetTextInput value={targetText} onChange={setTargetText} />
        <AudioUploader
          onSendClick = {handleSendClick}
        />
      </div>

      {showModal && (
        <LoginModal 
          onClose={() => setShowModal(false)} 
          onLogin={async (userData) => { 
            await login(userData); // 전역 로그인
            setShowModal(false); 
            // Check the access token
            console.log("user: ", userData);
          }}
        />
      )}
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
