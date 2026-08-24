function asQuestion(text) {
  if (!text) return "No user question captured yet.";
  return text.trim();
}

function asAnswer(answer, state) {
  if (answer) return answer.trim();
  if (state === "in_call" || state === "recording") {
    return "Waiting for the next assistant answer from the active relay.";
  }
  return "No assistant answer captured yet.";
}

export default function LiveTranscript({ snippet, answerText, state }) {
  return (
    <div className="qa-grid">
      <article className="transcript-card question-card">
        <p className="eyebrow">Question</p>
        <p>{asQuestion(snippet)}</p>
      </article>
      <article className="transcript-card answer-card">
        <p className="eyebrow">Answer</p>
        <p>{asAnswer(answerText, state)}</p>
      </article>
    </div>
  );
}
