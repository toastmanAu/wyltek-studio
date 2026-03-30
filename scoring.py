"""Image quality scoring — pixel-based metrics computed after every generation."""

import asyncio
import sqlite3
from pathlib import Path

import cv2
import numpy as np

DB_PATH = Path(__file__).parent / "data" / "scores.db"


def init_db():
    """Create scores table if not exists. Called once at startup."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("""
        CREATE TABLE IF NOT EXISTS scores (
            job_id TEXT PRIMARY KEY,
            model TEXT,
            backend TEXT,
            prompt TEXT,
            created TEXT,
            sharpness REAL,
            saturation REAL,
            brightness REAL,
            color_diversity REAL,
            contrast REAL,
            noise REAL,
            edge_density REAL,
            dynamic_range REAL
        )
    """)
    conn.commit()
    conn.close()


def compute_scores(image_path: str) -> dict:
    """Compute 8 pixel-based quality metrics. Returns dict of metric -> float."""
    img = cv2.imread(image_path)
    if img is None:
        return {}

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    h, w = gray.shape

    # 1. Sharpness — Laplacian variance (higher = sharper)
    laplacian = cv2.Laplacian(gray, cv2.CV_64F)
    sharpness = float(laplacian.var())

    # 2. Saturation — mean of S channel in HSV (0-255)
    saturation = float(hsv[:, :, 1].mean())

    # 3. Brightness — mean of V channel (0-255)
    brightness = float(hsv[:, :, 2].mean())

    # 4. Color diversity — unique colors in quantized space
    small = cv2.resize(img, (64, 64))
    quantized = (small // 32) * 32  # 8 levels per channel
    unique_colors = len(np.unique(quantized.reshape(-1, 3), axis=0))
    color_diversity = float(unique_colors)

    # 5. Contrast — std dev of luminance
    contrast = float(gray.astype(np.float64).std())

    # 6. Noise estimate — high-freq energy ratio
    img_energy = float((gray.astype(np.float64) ** 2).mean())
    lap_energy = float((laplacian ** 2).mean())
    noise = lap_energy / max(img_energy, 1e-6)

    # 7. Edge density — Canny edge pixel ratio
    edges = cv2.Canny(gray, 100, 200)
    edge_density = float(edges.sum() / 255.0) / (h * w)

    # 8. Dynamic range — 99th - 1st percentile luminance
    p1, p99 = np.percentile(gray, [1, 99])
    dynamic_range = float(p99 - p1)

    return {
        "sharpness": round(sharpness, 2),
        "saturation": round(saturation, 2),
        "brightness": round(brightness, 2),
        "color_diversity": round(color_diversity, 2),
        "contrast": round(contrast, 2),
        "noise": round(noise, 6),
        "edge_density": round(edge_density, 4),
        "dynamic_range": round(dynamic_range, 2),
    }


def save_scores(job_id: str, model: str, backend: str, prompt: str,
                created: str, scores: dict):
    """Insert scores into SQLite."""
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute(
        """INSERT OR REPLACE INTO scores
           (job_id, model, backend, prompt, created,
            sharpness, saturation, brightness, color_diversity,
            contrast, noise, edge_density, dynamic_range)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (job_id, model, backend, prompt, created,
         scores.get("sharpness"), scores.get("saturation"),
         scores.get("brightness"), scores.get("color_diversity"),
         scores.get("contrast"), scores.get("noise"),
         scores.get("edge_density"), scores.get("dynamic_range")),
    )
    conn.commit()
    conn.close()


def get_scores(job_id: str) -> dict | None:
    """Fetch scores for a single job."""
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT * FROM scores WHERE job_id = ?", (job_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def get_model_profiles() -> list[dict]:
    """Aggregated average scores per model."""
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    rows = conn.execute("""
        SELECT model, backend, COUNT(*) as image_count,
               ROUND(AVG(sharpness), 2) as avg_sharpness,
               ROUND(AVG(saturation), 2) as avg_saturation,
               ROUND(AVG(brightness), 2) as avg_brightness,
               ROUND(AVG(color_diversity), 2) as avg_color_diversity,
               ROUND(AVG(contrast), 2) as avg_contrast,
               ROUND(AVG(noise), 6) as avg_noise,
               ROUND(AVG(edge_density), 4) as avg_edge_density,
               ROUND(AVG(dynamic_range), 2) as avg_dynamic_range
        FROM scores GROUP BY model, backend
        ORDER BY image_count DESC
    """).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_scores_batch(job_ids: list[str]) -> list[dict]:
    """Fetch scores for multiple jobs."""
    if not job_ids:
        return []
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    placeholders = ",".join("?" * len(job_ids))
    rows = conn.execute(
        f"SELECT * FROM scores WHERE job_id IN ({placeholders})", job_ids
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


async def score_and_save(image_path: str, job_id: str, model: str,
                         backend: str, prompt: str, created: str) -> dict:
    """Async wrapper: compute scores + save to DB in thread executor."""
    loop = asyncio.get_event_loop()

    def _do():
        scores = compute_scores(image_path)
        if scores:
            save_scores(job_id, model, backend, prompt, created, scores)
        return scores

    return await loop.run_in_executor(None, _do)
