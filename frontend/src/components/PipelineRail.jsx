import { STEPS } from "../api.js";

export default function PipelineRail({ currentIndex, isError }) {
  return (
    <ol className="rail" aria-label="Generation pipeline">
      {STEPS.map((step, i) => {
        const done = currentIndex > i;
        const active = currentIndex === i && !isError;
        const state = done ? "done" : active ? "active" : "idle";
        return (
          <li key={step.key} className={`rail__step rail__step--${state}`}>
            <span className="rail__num">{String(i + 1).padStart(2, "0")}</span>
            <span className="rail__label">{step.label}</span>
            <span className="rail__dot" aria-hidden="true" />
          </li>
        );
      })}
    </ol>
  );
}
