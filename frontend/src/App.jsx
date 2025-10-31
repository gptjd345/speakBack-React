import React, { useState, useEffect } from "react";
import Header from "./components/Header";
import AudioUploader from "./components/AudioUploader";
import LoginModal from "./components/LoginModal";
import TargetTextInput from "./components/TargetTextInput";
import Home from "./pages/Home";
import "./styles/App.css";
import "./styles/Header.css";


function App() {
  const [isLoggedIn, setIsLoggedIn] = useState(false);
  const [showModal, setShowModal] = useState(false);
  const [targetText, setTargetText] = useState("");
  const [showLoginWarning, setShowLoginWarning] = useState(false);

  const handleSendClick = () => {
    if(!isLoggedIn) {
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

  return (
    <div className="App">
      <Header 
        isLoggedIn={isLoggedIn} 
        onLoginClick={() => setShowModal(true)} 
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
          onLogin={(data) => { setIsLoggedIn(true); setShowModal(false); 
            // Check the access token
            console.log("JWT access_token : ", data.access_token);
          }}
        />
      )}
    </div>
  );
}

export default App;
