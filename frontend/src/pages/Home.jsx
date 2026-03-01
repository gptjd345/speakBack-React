import React from "react";
import { useAuth } from "../contexts/AuthContext";
import "../styles/Home.css";

const FEATURES = [
  {
    icon: "🎯",
    title: "Precision Feedback",
    desc: "Word-level phoneme analysis identifies exactly where your pronunciation diverges from native speech.",
  },
  {
    icon: "⚡",
    title: "Instant Results",
    desc: "Get detailed AI-generated feedback in seconds — no waiting, no back-and-forth.",
  },
  {
    icon: "📊",
    title: "Track Progress",
    desc: "Session history lets you see how your score improves over time with consistent practice.",
  },
  {
    icon: "🌍",
    title: "Any Accent, Any Text",
    desc: "Practice any sentence in any language. Our model adapts to your target accent.",
  },
];

const STATS = [
  { num: "98%",  label: "Accuracy" },
  { num: "<2s",  label: "Analysis Time" },
  { num: "50+",  label: "Languages" },
  { num: "10K+", label: "Sessions" },
];

function Home({ onNavigate, onLoginClick }) {
  const { user } = useAuth();

  return (
    <div className="sb-home">
      {/* Hero */}
      <div className="sb-home-hero">
        <div className="sb-home-eyebrow">🎙 AI-Powered Pronunciation</div>
        <h1 className="sb-home-h1">
          Speak with<br /><em>confidence</em>
        </h1>
        <p className="sb-home-sub">
          Upload your voice or record live, then let our AI analyze your
          pronunciation and give you detailed, actionable feedback in seconds.
        </p>
        <div className="sb-home-cta-row">
          <button
            className="sb-btn sb-btn-primary sb-btn-lg"
            onClick={() => onNavigate("coach")}
          >
            Get started →
          </button>
          {!user && (
            <button
              className="sb-btn sb-btn-ghost sb-btn-lg"
              onClick={onLoginClick}
            >
              Sign in
            </button>
          )}
        </div>
      </div>

      {/* Feature Cards */}
      <div className="sb-home-features">
        {FEATURES.map((f, i) => (
          <div className="sb-feature-card" key={i}>
            <div className="sb-feature-icon">{f.icon}</div>
            <div className="sb-feature-title">{f.title}</div>
            <div className="sb-feature-desc">{f.desc}</div>
          </div>
        ))}
      </div>

      {/* Stats */}
      <div className="sb-home-stat-row">
        {STATS.map((s, i) => (
          <div className="sb-stat" key={i}>
            <div className="sb-stat-num">{s.num}</div>
            <div className="sb-stat-label">{s.label}</div>
          </div>
        ))}
      </div>
    </div>
  );
}

export default Home;
