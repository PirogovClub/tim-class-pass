import os
import sys
import json
import glob
import pendulum
import argparse

def parse_vtt_timestamps(ts_line: str):
    if '-->' not in ts_line:
        return None, None
    parts = ts_line.split('-->')
    start_time = parts[0].strip().split('.')[0]
    end_time = parts[1].strip().split('.')[0]
    return start_time, end_time

def is_time_between(target_ts: str, start_ts: str, end_ts: str) -> bool:
    try:
        if target_ts.count(':') == 1:
            target_ts = f"00:{target_ts}"
        if start_ts.count(':') == 1:
            start_ts = f"00:{start_ts}"
        if end_ts.count(':') == 1:
            end_ts = f"00:{end_ts}"
            
        target = pendulum.parse(target_ts, exact=True)
        start = pendulum.parse(start_ts, exact=True)
        end = pendulum.parse(end_ts, exact=True)
        return start <= target <= end
    except pendulum.parsing.exceptions.ParserError:
        return False

def stitch_transcript(vtt_file: str, gap_map: dict):
    video_dir = os.path.dirname(vtt_file)
    filename = os.path.basename(vtt_file)
    name, ext = os.path.splitext(filename)
    output_file = os.path.join(video_dir, f"{name}_enriched{ext}")
    
    with open(vtt_file, "r", encoding="utf-8") as f:
        lines = f.readlines()
        
    stitched_lines = []
    current_time_match = None
    
    for line in lines:
        stitched_lines.append(line)
        
        if '-->' in line:
            start_ts, end_ts = parse_vtt_timestamps(line)
            if start_ts and end_ts:
                # Find if any gap falls in this range
                for gap_ts, gap_desc in list(gap_map.items()):
                    if is_time_between(gap_ts, start_ts, end_ts):
                        current_time_match = gap_desc
                        del gap_map[gap_ts]
                        break
        elif line.strip() == "" and current_time_match:
            stitched_lines.insert(-1, f"\n[Visual Chart Description: {current_time_match}]\n")
            current_time_match = None

    if current_time_match:
        stitched_lines.append(f"\n[Visual Chart Description: {current_time_match}]\n")

    with open(output_file, "w", encoding="utf-8") as f:
        f.writelines(stitched_lines)
    print(f"Enriched transcript saved to {output_file}")


def run_stitcher(video_id: str):
    video_dir = os.path.join("data", video_id)
    targets_file = os.path.join(video_dir, "targets.json")
    
    if not os.path.exists(targets_file):
        print(f"Error: {targets_file} not found.")
        return
        
    with open(targets_file, "r", encoding="utf-8") as f:
        targets_data = json.load(f)

    vtt_files = glob.glob(os.path.join(video_dir, "*.vtt"))
    vtt_files = [f for f in vtt_files if not f.endswith("_enriched.vtt")]

    for vtt_file in vtt_files:
        filename = os.path.basename(vtt_file)
        gaps = targets_data.get(filename, [])
        
        if not gaps:
            print(f"No gaps found for {filename}, skipping.")
            continue
            
        # Map timestamp to vlm_description
        gap_map = {}
        for gap in gaps:
            if 'vlm_description' in gap:
                gap_map[gap['exact_timestamp']] = gap['vlm_description']
                
        if not gap_map:
            print(f"No VLM descriptions generated for {filename}, skipping.")
            continue
            
        print(f"Stitching Descriptions for {filename}")
        stitch_transcript(vtt_file, gap_map)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("video_id", help="Video ID directory in data/")
    args = parser.parse_args()
    
    run_stitcher(args.video_id)
