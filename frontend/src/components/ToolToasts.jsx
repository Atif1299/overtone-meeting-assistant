import React from "react";

const formatToolName = (str) => {
  if (!str) return "";
  return str
    .split("_")
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(" ");
};

export default function ToolToasts({ activeTools = {} }) {
  const toolList = Object.entries(activeTools);
  if (toolList.length === 0) return null;

  return (
    <div className="tool-toasts-container">
      {toolList.map(([id, tool]) => (
        <div key={id} className={`tool-toast ${tool.status === "done" ? "done" : ""}`}>
          {tool.status === "done" ? (
            <div className="tool-check">✓</div>
          ) : (
            <div className="tool-spinner"></div>
          )}
          <p className="tool-label">
            {tool.status === "done" ? `Completed ${formatToolName(tool.name)}` : `Executing ${formatToolName(tool.name)}...`}
          </p>
        </div>
      ))}
    </div>
  );
}
