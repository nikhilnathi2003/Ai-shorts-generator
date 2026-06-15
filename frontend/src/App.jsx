import { useEffect, useRef, useState } from "react";
import { startGeneration, fetchStatus, stageIndex } from "./api.js";
import PreviewStage from "./components/PreviewStage.jsx";
import PipelineRail from "./components/PipelineRail.jsx";

const EXAMPLES = [
  "The science of why we get déjà vu",
  "A Reddit story about the worst roommate ever",
  "Three deep-sea creatures that shouldn't exist",
];

export default function App() {
  const [input, setInput] = useState("");
  const [status, setStatus] = useState("idle"); // idle | running | done | error
  const [progress, setProgress] = useState(0);
  const [message, setMessage] = useState("");
  const [stage, setStage] = useState("queued");
  const [videoUrl, setVideoUrl] = useState(null);
  const [error, setError] = useState(null);
  const pollRef = useRef(null);

  useEffect(() => () => clearInterval(pollRef.current), []);

  function reset() {
    clearInterval(pollRef.current);
    setStatus("idle");
    setProgress(0);
    setMessage("");
    setStage("queued");
    setVideoUrl(null);
    setError(null);
  }

  async function handleGenerate() {
    if (input.trim().length < 3 || status === "running") return;
    setStatus("running");
    setProgress(2);
    setMessage("Waiting in queue");
    setStage("queued");
    setVideoUrl(null);
    setError(null);

    try {
      const { job_id } = await startGeneration(input.trim());
      pollRef.current = setInterval(() => poll(job_id), 1500);
    } catch (e) {
      setStatus("error");
      setError(e.message);
    }
  }

  async function poll(jobId) {
    try {
      const s = await fetchStatus(jobId);
      setProgress(s.progress ?? 0);
      setMessage(s.message ?? "");
      setStage(s.stage ?? "queued");

      if (s.stage === "done") {
        clearInterval(pollRef.current);
        setVideoUrl(s.video_url);
        setStatus("done");
      } else if (s.stage === "error") {
        clearInterval(pollRef.current);
        setError(s.error || "Something went wrong while building the video.");
        setStatus("error");
      }
    } catch (e) {
      clearInterval(pollRef.current);
      setError(e.message);
      setStatus("error");
    }
  }

  const idx = stageIndex(stage);
  const busy = status === "running";

  return (
    <div className="app">
      <header className="masthead">
        <div className="masthead__mark">◆</div>
        <span className="masthead__name">AI Shorts Generator</span>
        <span className="masthead__tag">topic in, captioned short out</span>
      </header>

      <main className="layout">
        <section className="panel">
          <h1 className="headline">
            Turn a sentence into a<br />
            <span className="headline__accent">captioned vertical short.</span>
          </h1>
          <p className="lede">
            Paste a topic or a story. It writes the script, voices it, generates the
            visuals, times the captions, and cuts the video.
          </p>

          <label className="field-label" htmlFor="topic">Topic or story</label>
          <textarea
            id="topic"
            className="textarea"
            placeholder="e.g. The Roman emperor who declared war on the sea…"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            disabled={busy}
            rows={5}
            maxLength={6000}
          />

          <div className="examples">
            {EXAMPLES.map((ex) => (
              <button
                key={ex}
                className="chip"
                onClick={() => setInput(ex)}
                disabled={busy}
                type="button"
              >
                {ex}
              </button>
            ))}
          </div>

          <div className="actions">
            {status === "done" || status === "error" ? (
              <button className="btn btn--primary" onClick={reset} type="button">
                Make another
              </button>
            ) : (
              <button
                className="btn btn--primary"
                onClick={handleGenerate}
                disabled={busy || input.trim().length < 3}
                type="button"
              >
                {busy ? "Working…" : "Generate short"}
              </button>
            )}
            {status === "done" && videoUrl && (
              <a className="btn btn--ghost" href={videoUrl} download target="_blank" rel="noreferrer">
                Download .mp4
              </a>
            )}
          </div>

          <PipelineRail currentIndex={idx} isError={status === "error"} />
        </section>

        <section className="showcase">
          <PreviewStage
            status={status}
            videoUrl={videoUrl}
            error={error}
            message={message}
            progress={progress}
          />
        </section>
      </main>

      <footer className="foot">
        Built with Groq · Edge-TTS · Pollinations · Whisper · FFmpeg
      </footer>
    </div>
  );
}
