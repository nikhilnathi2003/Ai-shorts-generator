export default function PreviewStage({ status, videoUrl, error, message, progress }) {
  // status: "idle" | "running" | "done" | "error"
  return (
    <div className={`stage stage--${status}`}>
      <div className="stage__frame">
        {status === "idle" && (
          <div className="stage__placeholder">
            <PlayGlyph />
            <p className="stage__hint">Your short shows up here</p>
            <p className="stage__sub">9:16 &middot; captioned &middot; ~60–90s</p>
          </div>
        )}

        {status === "running" && (
          <div className="stage__running">
            <span className="stage__live">
              <span className="stage__live-dot" />
              Rendering
            </span>
            <div className="stage__pct">{progress}%</div>
            <p className="stage__msg">{message}</p>
            <div className="stage__bar">
              <div className="stage__bar-fill" style={{ width: `${progress}%` }} />
            </div>
          </div>
        )}

        {status === "done" && videoUrl && (
          <video
            className="stage__video"
            src={videoUrl}
            controls
            playsInline
            autoPlay
            loop
          />
        )}

        {status === "error" && (
          <div className="stage__error">
            <p className="stage__error-title">Generation stopped</p>
            <p className="stage__error-msg">{error || message}</p>
          </div>
        )}
      </div>
    </div>
  );
}

function PlayGlyph() {
  return (
    <svg width="44" height="44" viewBox="0 0 44 44" fill="none" aria-hidden="true">
      <circle cx="22" cy="22" r="21" stroke="currentColor" strokeWidth="1.5" opacity="0.4" />
      <path d="M18 15.5 30 22l-12 6.5v-13Z" fill="currentColor" />
    </svg>
  );
}
