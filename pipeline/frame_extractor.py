import os
import json
import pendulum
import ffmpeg
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed

def _extract_single_frame(video_path: str, formatted_time: str, frame_path: str) -> tuple[bool, str | None]:
    if os.path.exists(frame_path):
        return True, None
    try:
        (
            ffmpeg
            .input(video_path, ss=formatted_time)
            .filter('scale', 1280, -1)
            .output(frame_path, vframes=1, qscale=2)
            .overwrite_output()
            .run(capture_stdout=True, capture_stderr=True)
        )
        return True, None
    except ffmpeg.Error as e:
        error = e.stderr.decode() if e.stderr else str(e)
        return False, error


def extract_frames(video_id: str, max_workers: int | None = None):
    video_dir = os.path.join("data", video_id)
    if not os.path.exists(video_dir):
        print(f"Directory {video_dir} not found.")
        return

    targets_file = os.path.join(video_dir, "targets.json")
    frames_dir = os.path.join(video_dir, "frames")
    os.makedirs(frames_dir, exist_ok=True)
    
    if not os.path.exists(targets_file):
        print(f"Error: {targets_file} not found. Run pipeline/gap_detector.py first.")
        return

    with open(targets_file, "r", encoding="utf-8") as f:
        try:
            targets_data = json.load(f)
        except json.JSONDecodeError:
            print("Error parsing targets.json")
            return

    possible_files = [f for f in os.listdir(video_dir) if f.startswith(video_id) and not f.endswith('.json') and not f.endswith('.vtt') and not f.endswith('.txt')]
    video_filename = [f for f in possible_files if os.path.isfile(os.path.join(video_dir, f))]
    
    if not video_filename:
        print(f"Warning: No video file found for video ID {video_id} in {video_dir}/")
        return
        
    video_path = os.path.join(video_dir, video_filename[0])

    tasks: list[tuple[str, str]] = []
    for vtt_filename, gaps in targets_data.items():
        print(f"Extracting {len(gaps)} frames based on {vtt_filename}")
        for gap in gaps:
            timestamp_str = gap['exact_timestamp']
            time_obj = pendulum.parse(timestamp_str, exact=True)
            formatted_time = time_obj.format("HH:mm:ss")
            safe_time_str = formatted_time.replace(":", "-")

            frame_filename = f"{video_id}_frame_{safe_time_str}.jpg"
            frame_path = os.path.join(frames_dir, frame_filename)

            gap['frame_path'] = frame_path
            tasks.append((formatted_time, frame_path))

    if not tasks:
        print("No frames to extract.")
    else:
        if max_workers is None:
            max_workers = min(8, len(tasks))
        try:
            max_workers = int(max_workers)
        except (TypeError, ValueError):
            max_workers = 1
        if max_workers < 1:
            max_workers = 1
        if max_workers > 8:
            max_workers = 8

        if max_workers == 1 or len(tasks) == 1:
            for formatted_time, frame_path in tasks:
                if os.path.exists(frame_path):
                    print(f"Frame already exists: {frame_path}")
                    continue
                print(f"  Extracting at {formatted_time} -> {os.path.basename(frame_path)}")
                ok, err = _extract_single_frame(video_path, formatted_time, frame_path)
                if not ok:
                    print(f"FFmpeg error: {err}")
        else:
            print(f"Using {max_workers} workers to extract {len(tasks)} frames...")
            futures = []
            with ThreadPoolExecutor(max_workers=min(max_workers, len(tasks))) as executor:
                for formatted_time, frame_path in tasks:
                    if os.path.exists(frame_path):
                        print(f"Frame already exists: {frame_path}")
                        continue
                    futures.append(
                        executor.submit(_extract_single_frame, video_path, formatted_time, frame_path)
                    )
                for future in as_completed(futures):
                    ok, err = future.result()
                    if not ok:
                        print(f"FFmpeg error: {err}")
                
    with open(targets_file, "w", encoding="utf-8") as f:
        json.dump(targets_data, f, indent=2)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("video_id", help="Video ID directory in data/")
    parser.add_argument("--workers", type=int, default=None, help="Max workers for frame extraction (cap 8 recommended)")
    args = parser.parse_args()
    
    extract_frames(args.video_id, max_workers=args.workers)
