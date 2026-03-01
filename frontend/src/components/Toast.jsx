import React from "react";
// .sb-toast styles are in global.css

function Toast({ message, show }) {
  return (
    <div className={`sb-toast ${show ? "show" : ""}`}>
      {message}
    </div>
  );
}

export default Toast;
