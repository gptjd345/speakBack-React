import React from "react";
import { useAuth } from "../contexts/AuthContext";
import "../styles/Sidebar.css";

const NAV_ITEMS = [
  { id: "home",  icon: "🏠", label: "Home" },
  { id: "coach", icon: "🎤", label: "Pronunciation Coach" },
  { id: "lab",   icon: "🧪", label: "Practice Lab", soon: true },
];

function Sidebar({ active, onNavigate }) {
  const { user, logout } = useAuth();

  return (
    <aside className="sb-sidebar">
      {/* Logo */}
      <div className="sb-sidebar-logo">
        <div className="sb-logo-wordmark">
          Speak<span className="sb-logo-dot">Back</span>
        </div>
      </div>

      {/* Navigation */}
      <nav className="sb-nav">
        <div className="sb-nav-label">Menu</div>
        {NAV_ITEMS.map((item) => (
          <button
            key={item.id}
            className={`sb-nav-item ${active === item.id ? "active" : ""}`}
            onClick={() => onNavigate(item.id)}
          >
            <span className="nav-icon">{item.icon}</span>
            {item.label}
            {item.soon && <span className="sb-soon-badge">Soon</span>}
          </button>
        ))}
      </nav>

      {/* User Footer */}
      <div className="sb-sidebar-footer">
        {user ? (
          <div className="sb-user-pill">
            <div className="sb-user-avatar">
              {user.username?.[0]?.toUpperCase() || "U"}
            </div>
            <div className="sb-user-name">{user.username}</div>
            <button className="sb-user-logout" onClick={logout}>
              Sign out
            </button>
          </div>
        ) : (
          <div className="sb-sidebar-not-signed">Not signed in</div>
        )}
      </div>
    </aside>
  );
}

export default Sidebar;
