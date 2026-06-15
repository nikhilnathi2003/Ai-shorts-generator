const API_BASE = (import.meta.env.VITE_API_BASE || "http://localhost:8000").replace(/\/$/, "");

// Ordered pipeline steps shown in the UI. Each maps to one or more backend stages.
export const STEPS = [
  { key: "script", label: "Script" },
  { key: "voiceover", label: "Voiceover" },
  { key: "images", label: "Visuals" },
  { key: "captions", label: "Captions" },
  { key: "assembling", label: "Assemble" },
  { key: "uploading", label: "Upload" },
];

const STAGE_TO_INDEX = {
  queued: -1,
  script: 0,
  voiceover: 1,
  images: 2,
  captions: 3,
  assembling: 4,
  uploading: 5,
  done: 6,
  error: -1,
};

export function stageIndex(stage) {
  return STAGE_TO_INDEX[stage] ?? -1;
}

export async function startGeneration(input) {
  const res = await fetch(`${API_BASE}/api/generate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ input }),
  });
  if (!res.ok) {
    const detail = await safeDetail(res);
    throw new Error(detail || `Request failed (${res.status})`);
  }
  return res.json(); // { job_id }
}

export async function fetchStatus(jobId) {
  const res = await fetch(`${API_BASE}/api/status/${jobId}`);
  if (!res.ok) {
    const detail = await safeDetail(res);
    throw new Error(detail || `Status check failed (${res.status})`);
  }
  return res.json();
}

async function safeDetail(res) {
  try {
    const data = await res.json();
    return data.detail;
  } catch {
    return null;
  }
}
