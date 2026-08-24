import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App.jsx";
import "./index.css";

// StrictMode intentionally double-mounts effects in development, which creates
// two concurrent WebSocket + WavStreamPlayer instances → double audio output.
// This page is a Recall.ai bot output-media surface, not a typical React app,
// so the double-mount side effect is harmful rather than helpful.
ReactDOM.createRoot(document.getElementById("root")).render(<App />);
