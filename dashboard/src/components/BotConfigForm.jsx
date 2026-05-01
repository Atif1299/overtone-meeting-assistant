export default function BotConfigForm({
  value,
  presentations = [],
  agents = [],
  onChange,
  onSubmit,
  disabled,
}) {
  const selectedAgent = agents.find((agent) => agent.agent_name === (value.agent_name || "default"));
  const suggestedPresentationId = selectedAgent?.active_presentation_id || "";
  const selectedPresentation = presentations.find(
    (presentation) => presentation.presentation_id === value.presentation_id
  );

  function handleAgentChange(nextAgentName) {
    const nextAgent = agents.find((agent) => agent.agent_name === nextAgentName);
    const nextPresentation = nextAgent?.active_presentation_id || value.presentation_id;
    onChange({
      ...value,
      agent_name: nextAgentName,
      presentation_id: nextPresentation || value.presentation_id,
    });
  }

  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        onSubmit();
      }}
      className="stack-gap"
    >
      <div className="form-grid">
        <label className="field">
          Agent
          {agents.length > 0 ? (
            <select
              className="input"
              value={value.agent_name || "default"}
              onChange={(e) => handleAgentChange(e.target.value)}
            >
              {agents.map((agent) => (
                <option key={agent.agent_name} value={agent.agent_name}>
                  {agent.agent_name}
                  {agent.active_version ? ` (v${agent.active_version})` : ""}
                </option>
              ))}
            </select>
          ) : (
            <input
              className="input"
              value={value.agent_name || "default"}
              onChange={(e) => handleAgentChange(e.target.value)}
            />
          )}
        </label>
        <label className="field">
          Bot name
          <input
            className="input"
            value={value.bot_name}
            required
            onChange={(e) => onChange({ ...value, bot_name: e.target.value })}
          />
        </label>
      </div>
      {selectedAgent ? (
        <div className="helper-text">
          Active profile: <strong>{selectedAgent.agent_name}</strong>
          {selectedAgent.active_version ? ` v${selectedAgent.active_version}` : ""}.{" "}
          {suggestedPresentationId
            ? `Default knowledge base: ${suggestedPresentationId}.`
            : "No default knowledge base set for this agent."}
        </div>
      ) : null}
      <div className="form-grid">
        <label className="field">
          Meeting URL (Teams / Zoom / Meet)
          <input
            className="input"
            type="url"
            placeholder="https://teams.microsoft.com/l/meetup-join/..."
            value={value.meeting_url}
            required
            onChange={(e) => onChange({ ...value, meeting_url: e.target.value })}
          />
        </label>
        <label className="field">
          Presentation (knowledge base filter)
          {presentations.length > 0 ? (
            <select
              className="input"
              value={value.presentation_id || ""}
              onChange={(e) => onChange({ ...value, presentation_id: e.target.value })}
            >
              <option value="" disabled>
                Select presentation
              </option>
              {presentations.map((presentation) => (
                <option key={presentation.presentation_id} value={presentation.presentation_id}>
                  {presentation.filename} ({presentation.presentation_id})
                </option>
              ))}
            </select>
          ) : (
            <input
              className="input"
              value={value.presentation_id || ""}
              required
              onChange={(e) => onChange({ ...value, presentation_id: e.target.value })}
            />
          )}
        </label>
      </div>
      {selectedPresentation ? (
        <div className="helper-text">
          RAG filtering scope: <strong>{selectedPresentation.presentation_id}</strong> only.
        </div>
      ) : null}
      <div className="form-grid">
        <label className="field">
          Agent mode
          <select
            className="input"
            value={value.agent_mode || "realtime"}
            onChange={(e) => onChange({ ...value, agent_mode: e.target.value })}
          >
            <option value="realtime">Realtime (primary)</option>
            <option value="webhook">Webhook fallback</option>
          </select>
        </label>
        <label className="field">
          Auto-present first N slides
          <input
            className="input"
            type="number"
            min="0"
            max="200"
            placeholder="0 = Q&A only"
            value={value.auto_present_pages ?? ""}
            onChange={(e) =>
              onChange({
                ...value,
                auto_present_pages: e.target.value ? parseInt(e.target.value, 10) : null,
              })
            }
          />
        </label>
      </div>
      {value.auto_present_pages > 0 && (
        <div className="helper-text">
          Bot will auto-narrate slides 1–{value.auto_present_pages}, then switch to Q&A mode.
        </div>
      )}
      <button type="submit" disabled={disabled} className="button button-primary">
        {disabled ? "Launching..." : "Connect bot"}
      </button>
    </form>
  );
}
