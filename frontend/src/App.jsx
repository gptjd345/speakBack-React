import React, { useState, useEffect } from "react";
import Header from "./components/Header";
import AudioUploader from "./components/AudioUploader";
import LoginModal from "./components/LoginModal";
import TargetTextInput from "./components/TargetTextInput";
import { AuthProvider } from "./contexts/AuthContext";
import { useAuth } from "./contexts/AuthContext";
import useLangGraph from "./hooks/useLangGraph";
import ResultViewer from "./components/ResultViewer";

import Home from "./pages/Home";
import "./styles/App.css";
import "./styles/Header.css";


function AppContent() {
  const { user, login, logout } = useAuth(); // 전역 로그인 상태 사용
  const [showModal, setShowModal] = useState(false);
  const [targetText, setTargetText] = useState("");
  const [showLoginWarning, setShowLoginWarning] = useState(false);
  const [file, setFile] = useState(null); // file 상태를 부모로 끌어올림

  // langgraph API Hooks
  const { loading, result, error, runLangGraphProcess } = useLangGraph(); 

  // file upload + excute 
  const handleSendClick = () => {
    if(!user) {
      setShowLoginWarning(true);
    } else {
      setShowLoginWarning(false);
      // 실제 LangGraph 처리
    }

    // if login OK -> Langgraph execute
    runLangGraphProcess(file, user, targetText);
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

      <div className="intro-box">
        <h2 className="intro-title">Speak with confidence</h2>
        <p className="intro-text">
          Welcome to SpeakBack! 🎉<br />
          Enter your text and upload your voice recording.<br />
          Our AI will analyze your pronunciation and provide detailed feedback.<br />
          Please log in to get started.<br />
        </p>
      </div>
  
      <div className="main-content">
        <h1>Pronunciation Coach 🎤</h1>
        <TargetTextInput value={targetText} onChange={setTargetText} />

        <AudioUploader
          file={file}       // 부모 상태 전달
          setFile={setFile} // 부모상태 업데이트 함수전달
          onSendClick = {handleSendClick}
        />
        {loading && <p>Running…</p>}
        {error && <p>Error: {error}</p>}
        {result && <ResultViewer data={result} />}
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
