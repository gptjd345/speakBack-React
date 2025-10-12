import React from "react";

const Home = ({ loggedIn }) => {
  if (!loggedIn) {
    return <div style={{textAlign:"center", marginTop:"30px"}}>Please login to access the pronunciation coach.</div>;
  }

  return (
    <div className="main-content">
      {/* Name input, Target text, AudioUploader, Send button, Results */}
      {/* 여기서 Streamlit layout 참고해서 컴포넌트 연결 예정 */}
      <h1>Pronunciation Coach 🎤</h1>
    </div>
  );
};

export default Home;
