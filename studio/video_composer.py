"""Video compositor — builds MP4 from timeline spec via FFmpeg subprocess."""

import asyncio
import os
import shutil
import uuid
from pathlib import Path

# Available xfade transition types
TRANSITIONS = [
    "fade", "dissolve", "slideleft", "slideright", "slideup", "slidedown",
    "wipeleft", "wiperight", "wipeup", "wipedown",
    "smoothleft", "smoothright", "smoothup", "smoothdown",
    "circlecrop", "rectcrop", "distance", "fadeblack", "fadewhite",
    "radial", "smoothleft",
]

# Ken Burns zoompan presets
KEN_BURNS = {
    "none": None,
    "zoom-in": "z='min(zoom+0.0015,1.3)':x='(iw-iw/zoom)/2':y='(ih-ih/zoom)/2'",
    "zoom-out": "z='if(eq(on,1),1.3,max(zoom-0.0015,1.0))':x='(iw-iw/zoom)/2':y='(ih-ih/zoom)/2'",
    "pan-left": "z=1.1:x='if(eq(on,1),0,min(x+2,iw-iw/zoom))':y='(ih-ih/zoom)/2'",
    "pan-right": "z=1.1:x='if(eq(on,1),iw-iw/zoom,max(x-2,0))':y='(ih-ih/zoom)/2'",
}

DEFAULT_FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"


async def render_video(timeline: dict, project_dir: Path, output_path: str,
                       on_progress=None) -> dict:
    """Render a full video from a timeline spec.

    Pipeline:
    1. Per-clip: scale + ken burns → temp clip MP4s
    2. Xfade chain: iterative pairwise merge
    3. Text overlays: single pass with drawtext
    4. Audio mix: mux narration + music
    """
    clips = timeline.get("clips", [])
    if not clips:
        raise ValueError("Timeline has no clips")

    resolution = timeline.get("resolution", [1920, 1080])
    fps = timeline.get("fps", 30)
    w, h = resolution

    job_id = str(uuid.uuid4())[:8]
    tmp_dir = project_dir / "video" / f".tmp_{job_id}"
    tmp_dir.mkdir(parents=True, exist_ok=True)

    try:
        # Phase 1: Per-clip preparation (0-40%)
        clip_files = []
        for i, clip in enumerate(clips):
            if on_progress:
                pct = int((i / len(clips)) * 40)
                await on_progress(pct, f"Preparing clip {i+1}/{len(clips)}")

            image_path = _resolve_image(clip["asset"], project_dir)
            if not image_path:
                raise FileNotFoundError(f"Asset not found: {clip['asset']}")

            clip_path = str(tmp_dir / f"clip_{i:03d}.mp4")
            await _render_clip(image_path, clip_path, clip, w, h, fps)
            clip_files.append(clip_path)

        # Phase 2: Xfade chain (40-70%)
        if len(clip_files) == 1:
            stitched = clip_files[0]
        else:
            stitched = clip_files[0]
            for i in range(1, len(clip_files)):
                if on_progress:
                    pct = 40 + int((i / (len(clip_files) - 1)) * 30)
                    await on_progress(pct, f"Joining clip {i+1}/{len(clip_files)}")

                merged = str(tmp_dir / f"merged_{i:03d}.mp4")
                clip = clips[i]
                trans_type = clip.get("transition", {}).get("type", "fade")
                trans_dur = clip.get("transition", {}).get("duration", 1.0)

                # Get duration of current stitched video
                stitch_dur = await _get_duration(stitched)
                offset = max(stitch_dur - trans_dur, 0)

                await _xfade(stitched, clip_files[i], merged, trans_type, trans_dur, offset)
                stitched = merged

        # Phase 3: Text overlays (70-85%)
        text_clips = [(i, c) for i, c in enumerate(clips) if c.get("text_overlay")]
        if text_clips:
            if on_progress:
                await on_progress(70, "Adding text overlays")
            texted = str(tmp_dir / "texted.mp4")
            await _apply_text_overlays(stitched, texted, clips, timeline)
            stitched = texted
        if on_progress:
            await on_progress(85, "Text overlays done")

        # Phase 4: Audio mix (85-100%)
        audio = timeline.get("audio", {})
        narration = audio.get("narration")
        music = audio.get("music")

        if narration or music:
            if on_progress:
                await on_progress(85, "Mixing audio")
            final = str(tmp_dir / "final.mp4")
            await _mix_audio(stitched, final, narration, music, project_dir)
            stitched = final

        if on_progress:
            await on_progress(95, "Finalizing")

        # Move to output
        shutil.copy2(stitched, output_path)

        # Get final duration
        duration = await _get_duration(output_path)

        if on_progress:
            await on_progress(100, "Done")

        return {
            "duration": round(duration, 2),
            "file_size": os.path.getsize(output_path),
            "clips": len(clips),
            "resolution": f"{w}x{h}",
        }

    finally:
        # Clean up temp files
        shutil.rmtree(tmp_dir, ignore_errors=True)


async def render_preview_frame(timeline: dict, project_dir: Path,
                               playhead: float, output_path: str,
                               resolution: list = None) -> str:
    """Render a single frame at the given playhead time."""
    clips = timeline.get("clips", [])
    if not clips:
        return None

    resolution = resolution or timeline.get("resolution", [1920, 1080])
    w, h = resolution

    # Find which clip the playhead is in
    current_time = 0
    target_clip = clips[0]
    time_in_clip = playhead

    for i, clip in enumerate(clips):
        clip_dur = clip.get("duration", 5.0)
        trans_dur = clip.get("transition", {}).get("duration", 1.0) if i > 0 else 0
        effective_start = current_time - trans_dur if i > 0 else 0

        if playhead < current_time + clip_dur - (trans_dur if i < len(clips) - 1 else 0):
            target_clip = clip
            time_in_clip = playhead - current_time
            break
        current_time += clip_dur - trans_dur

    image_path = _resolve_image(target_clip["asset"], project_dir)
    if not image_path:
        return None

    # Render single frame with Ken Burns at the right time offset
    cmd = [
        "ffmpeg", "-y", "-loop", "1", "-i", str(image_path),
        "-vf", f"scale={w}:{h}:force_original_aspect_ratio=decrease,"
               f"pad={w}:{h}:(ow-iw)/2:(oh-ih)/2:black",
        "-frames:v", "1",
        str(output_path),
    ]

    proc = await asyncio.create_subprocess_exec(
        *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    await proc.communicate()
    return output_path


# --- Internal helpers ---

def _resolve_image(asset_filename: str, project_dir: Path) -> Path | None:
    """Find an image in the project or via storage resolver."""
    # Check project images dir first
    p = project_dir / "images" / asset_filename
    if p.exists():
        return p

    # Fall back to storage resolver
    import storage
    resolved = storage.resolve_asset(asset_filename)
    return resolved


async def _render_clip(image_path: str | Path, output_path: str,
                       clip: dict, w: int, h: int, fps: int):
    """Render a single image into a video clip with Ken Burns."""
    duration = clip.get("duration", 5.0)
    frames = int(duration * fps)
    kb = clip.get("ken_burns", {})
    kb_effect = kb.get("effect", "none")

    # Build filter chain
    # For Ken Burns: feed a single frame to zoompan which controls duration via d=
    # For static: loop the image for the clip duration
    if kb_effect != "none" and kb_effect in KEN_BURNS:
        zp = KEN_BURNS[kb_effect]
        vf = (f"scale=3840:2160:force_original_aspect_ratio=decrease,"
              f"pad=3840:2160:(ow-iw)/2:(oh-ih)/2:black,"
              f"zoompan={zp}:d={frames}:s={w}x{h}:fps={fps},"
              f"format=yuv420p")
        # Single image input (no loop) — zoompan generates all frames from it
        input_args = ["-i", str(image_path)]
    else:
        vf = (f"scale={w}:{h}:force_original_aspect_ratio=decrease,"
              f"pad={w}:{h}:(ow-iw)/2:(oh-ih)/2:black,"
              f"format=yuv420p")
        input_args = ["-loop", "1", "-t", str(duration), "-i", str(image_path)]

    cmd = [
        "ffmpeg", "-y",
        *input_args,
        "-vf", vf,
        "-c:v", "libx264", "-preset", "fast", "-crf", "23",
        "-pix_fmt", "yuv420p", "-r", str(fps),
        str(output_path),
    ]

    proc = await asyncio.create_subprocess_exec(
        *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    _, stderr = await proc.communicate()
    if proc.returncode != 0:
        raise RuntimeError(f"FFmpeg clip render failed: {stderr.decode()[-500:]}")


async def _xfade(input_a: str, input_b: str, output: str,
                 transition: str, duration: float, offset: float):
    """Apply xfade transition between two video files."""
    if transition not in TRANSITIONS:
        transition = "fade"

    cmd = [
        "ffmpeg", "-y",
        "-i", input_a, "-i", input_b,
        "-filter_complex",
        f"[0:v][1:v]xfade=transition={transition}:duration={duration}:offset={offset},format=yuv420p",
        "-c:v", "libx264", "-preset", "fast", "-crf", "23",
        "-pix_fmt", "yuv420p",
        output,
    ]

    proc = await asyncio.create_subprocess_exec(
        *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    _, stderr = await proc.communicate()
    if proc.returncode != 0:
        raise RuntimeError(f"FFmpeg xfade failed: {stderr.decode()[-500:]}")


async def _apply_text_overlays(input_path: str, output_path: str,
                               clips: list, timeline: dict):
    """Apply all text overlays in a single FFmpeg pass."""
    filters = []
    current_time = 0

    for i, clip in enumerate(clips):
        clip_dur = clip.get("duration", 5.0)
        trans_dur = clip.get("transition", {}).get("duration", 1.0) if i > 0 else 0

        overlay = clip.get("text_overlay")
        if overlay and overlay.get("text"):
            start = current_time + overlay.get("start_offset", 0)
            end = start + overlay.get("display_duration", clip_dur)
            text = overlay["text"].replace("'", "\\'").replace(":", "\\:")
            size = overlay.get("font_size", 48)
            color = overlay.get("font_color", "white")

            pos = overlay.get("position", "center")
            if pos == "center":
                x, y = "(w-tw)/2", "(h-th)/2"
            elif pos == "bottom":
                x, y = "(w-tw)/2", "h-th-60"
            elif pos == "top":
                x, y = "(w-tw)/2", "60"
            else:
                x, y = "(w-tw)/2", "(h-th)/2"

            font_path = DEFAULT_FONT
            f = (f"drawtext=text='{text}':fontfile={font_path}:fontsize={size}"
                 f":fontcolor={color}:x={x}:y={y}"
                 f":enable='between(t,{start},{end})'")
            filters.append(f)

        current_time += clip_dur - trans_dur

    if not filters:
        shutil.copy2(input_path, output_path)
        return

    vf = ",".join(filters)
    cmd = [
        "ffmpeg", "-y", "-i", input_path,
        "-vf", vf,
        "-c:v", "libx264", "-preset", "fast", "-crf", "23",
        "-c:a", "copy",
        output_path,
    ]

    proc = await asyncio.create_subprocess_exec(
        *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    _, stderr = await proc.communicate()
    if proc.returncode != 0:
        raise RuntimeError(f"FFmpeg text overlay failed: {stderr.decode()[-500:]}")


async def _mix_audio(video_path: str, output_path: str,
                     narration: dict | None, music: dict | None,
                     project_dir: Path):
    """Mix narration and/or music into the video."""
    inputs = ["-i", video_path]
    filter_parts = []
    audio_inputs = []

    if narration and narration.get("asset"):
        nar_path = _resolve_image(narration["asset"], project_dir)  # reuse resolver
        if nar_path and nar_path.exists():
            idx = len(inputs) // 2
            inputs.extend(["-i", str(nar_path)])
            vol = narration.get("volume", 1.0)
            filter_parts.append(f"[{idx}:a]volume={vol}[nar]")
            audio_inputs.append("[nar]")

    if music and music.get("asset"):
        mus_path = _resolve_image(music["asset"], project_dir)
        if mus_path and mus_path.exists():
            idx = len(inputs) // 2
            inputs.extend(["-i", str(mus_path)])
            vol = music.get("volume", 0.3)
            filter_parts.append(f"[{idx}:a]volume={vol}[bgm]")
            audio_inputs.append("[bgm]")

    if not audio_inputs:
        shutil.copy2(video_path, output_path)
        return

    if len(audio_inputs) == 1:
        mix = audio_inputs[0]
    else:
        filter_parts.append(f"{''.join(audio_inputs)}amix=inputs={len(audio_inputs)}:duration=longest[mix]")
        mix = "[mix]"

    filter_complex = ";".join(filter_parts)

    cmd = [
        "ffmpeg", "-y",
        *inputs,
        "-filter_complex", filter_complex,
        "-map", "0:v",
        "-map", mix,
        "-c:v", "copy",
        "-c:a", "aac", "-b:a", "192k",
        "-shortest",
        output_path,
    ]

    proc = await asyncio.create_subprocess_exec(
        *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    _, stderr = await proc.communicate()
    if proc.returncode != 0:
        raise RuntimeError(f"FFmpeg audio mix failed: {stderr.decode()[-500:]}")


async def _get_duration(filepath: str) -> float:
    """Get video duration via ffprobe."""
    cmd = [
        "ffprobe", "-v", "quiet", "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1", filepath,
    ]
    proc = await asyncio.create_subprocess_exec(
        *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    stdout, _ = await proc.communicate()
    try:
        return float(stdout.decode().strip())
    except (ValueError, AttributeError):
        return 0.0
