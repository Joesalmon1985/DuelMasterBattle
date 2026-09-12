#!/usr/bin/env python3
"""
Build a training dataset from Duel Master Battle existing sprites.

Discovers eligible source art, extracts individual sprites/frames from sprite sheets,
deduplicates, balances categories, and outputs a structured training dataset.
"""

import os
import re
import json
import shutil
from pathlib import Path
from PIL import Image
from collections import defaultdict

# Configuration
REPO_ROOT = Path("C:/Users/joesa/Documents/Cursor/DuelMaster/DuelMasterBattle")
CHAR_DIR = REPO_ROOT / "godot_project" / "assets" / "pixel" / "chars"
TILE_DIR = REPO_ROOT / "godot_project" / "assets" / "pixel" / "tiles"
PROP_DIR = REPO_ROOT / "godot_project" / "assets" / "pixel" / "props"
TILESET_DIR = REPO_ROOT / "godot_project" / "assets" / "sprites"
OUTPUT_DIR = REPO_ROOT / "training" / "dmb_world_pixel_v1"

CATEGORIES = {
    "character": {
        "dir": CHAR_DIR,
        "size": (16, 24),
        "frames_per_dir": 2,  # _0 and _1
        "directions": ["down", "left", "right", "up"],
        "exclude_patterns": [],
    },
    "tile": {
        "dir": TILE_DIR,
        "size": (16, 16),
        "frames_per_dir": 1,
        "directions": [],  # static tiles, no directions
        "exclude_patterns": [],
    },
    "prop": {
        "dir": PROP_DIR,
        "size": None,  # variable sizes
        "frames_per_dir": 1,
        "directions": [],
        "exclude_patterns": [],
    },
}


def discover_sprites(category_config):
    """Discover all sprites for a given category."""
    sprite_dir = category_config["dir"]
    if not sprite_dir.is_dir():
        print(f"  WARNING: Directory not found: {sprite_dir}")
        return {}

    files = [f for f in os.listdir(sprite_dir) if f.lower().endswith('.png')]
    discoveries = defaultdict(list)

    for f in sorted(files):
        path = sprite_dir / f
        try:
            img = Image.open(path)
        except Exception:
            continue

        # Determine key characteristics
        w, h = img.size

        # Group by base name (remove _0.png, _1.png suffix)
        base_name = re.sub(r'_\d\.png$', '', f)

        # Check if it's a directional frame
        direction = None
        frame_num = None

        # Pattern: name_direction_frame.png e.g. woodcutter_down_0.png
        m = re.match(r'(.+?)_(down|left|right|up)_(\d+)\.png$', f)
        if m:
            base = m.group(1)
            direction = m.group(2)
            frame_num = int(m.group(3))
        else:
            # Could be name_0.png without direction, or just name.png
            m2 = re.match(r'(.+?)_(\d+)\.png$', f)
            if m2:
                base = m2.group(1)
                frame_num = int(m2.group(2))
            else:
                base = f[:-4]  # remove .png
                frame_num = None

        discoveries[base].append({
            "filename": f,
            "path": path,
            "width": w,
            "height": h,
            "direction": direction,
            "frame": frame_num,
        })

    return discoveries


def extract_individual_frames(discoveries, category_config):
    """Extract individual sprite frames from discovered files."""
    frames = []
    base_groups = defaultdict(list)

    for item in discoveries.values():
        for itm in item:
            base_key = itm["filename"]
            # Use the full filename as key for now
            base_groups[base_key].append(itm)

    for base_key, items in base_groups.items():
        # Sort by direction then frame
        items.sort(key=lambda x: (x.get("direction", ""), x.get("frame", 0)))

        for itm in items:
            try:
                img = Image.open(itm["path"])
                # Crop to exact game dimensions if needed
                target_size = category_config["size"]
                if target_size and img.size != target_size:
                    # Scale using nearest-neighbour
                    img = img.resize(target_size, Image.NEAREST)

                # Generate output filename
                dir_suffix = ""
                if itm.get("direction"):
                    dir_suffix = f"_{itm['direction']}"
                if itm.get("frame") is not None:
                    dir_suffix += f"{itm['frame']}"

                out_filename = f"{base_key.split('_')[0]}{dir_suffix}.png" if dir_suffix else f"{base_key}.png"

                frames.append({
                    "source": str(itm["path"]),
                    "output": out_filename,
                    "direction": itm.get("direction"),
                    "frame": itm.get("frame"),
                    "width": img.width,
                    "height": img.height,
                    "transparent_edges": _count_transparent_edges(img),
                })
            except Exception as e:
                print(f"  ERROR processing {itm['path']}: {e}")

    return frames


def _count_transparent_edges(img):
    """Count how many edge pixels are transparent - helps assess quality."""
    datas = img.getdata()
    w, h = img.size

    # Check border pixels
    transparent_count = 0
    total_border = 0

    # Top and bottom rows
    for x in range(w):
        total_border += 1
        if datas[x][3] == 0:
            transparent_count += 1
        total_border += 1
        if datas[(x + (w - 1)) * h + (h - 1) if False else 0][3] == 0:
            # Simplified: just count corners and edges
            pass

    # Left and right columns (excluding corners already counted)
    for y in range(1, h - 1):
        total_border += 1
        idx = y * w + 0
        if datas[idx][3] == 0:
            transparent_count += 1
        total_border += 1
        idx = y * w + (w - 1)
        if datas[idx][3] == 0:
            transparent_count += 1

    return {
        "transparent_pixels": transparent_count,
        "total_border_pixels": total_border if total_border > 0 else 1,
        "ratio": transparent_count / max(total_border, 1),
    }


def deduplicate_frames(frames_list):
    """Remove exact duplicate frames based on pixel data."""
    unique = []
    seen_hashes = set()

    for frame in frames_list:
        try:
            img = Image.open(frame["path"])
            # Generate a hash based on the image data
            h = img.tobytes()
            if h in seen_hashes:
                print(f"  DUPLICATE: {frame['output']} (hash match)")
                continue
            seen_hashes.add(h)
        except Exception:
            pass

        unique.append(frame)

    return unique


def balance_categories(all_frames_by_category):
    """Balance frames across categories to avoid overrepresentation."""
    total_per_category = defaultdict(int)
    for category, frames in all_frames_by_category.items():
        total_per_category[category] = len(frames)

    # Calculate target per category (cap at reasonable amount)
    max_per_category = 30  # reasonable cap for first model
    balanced = {}

    for category, frames in all_frames_by_category.items():
        count = min(len(frames), max_per_category)
        balanced[category] = frames[:count]
        if len(frames) > count:
            print(f"  CAP: {category} capped at {count}/{len(frames)} frames")

    return balanced


def generate_manifest(train_files, val_files, all_sources):
    """Generate manifest CSV mapping training images to source repos."""
    manifest_rows = []

    # Training files
    for info in train_files:
        manifest_rows.append({
            "filename": info["output"],
            "source_repo": info["source"],
            "category": info.get("category", "unknown"),
            "direction": info.get("direction", ""),
            "frame": info.get("frame", ""),
        })

    # Validation files
    for info in val_files:
        manifest_rows.append({
            "filename": info["output"],
            "source_repo": info["source"],
            "category": info.get("category", "unknown"),
            "direction": info.get("direction", ""),
            "frame": info.get("frame", ""),
        })

    return manifest_rows


def main():
    print("=" * 60)
    print("DUEL MASTER BATTLE - SPRITE TRAINING DATASET BUILDER")
    print("=" * 60)
    print()

    # Step 1: Discover all sprite categories
    print("Phase 1: Discovering existing sprite assets...")
    all_discoveries = {}

    for cat_name, config in CATEGORIES.items():
        discoveries = discover_sprites(config)
        all_discoveries[cat_name] = discoveries
        print(f"  {cat_name}: {sum(len(v) for v in discoveries.values())} total frame references")

    print()

    # Step 2: Extract individual frames
    print("Phase 2: Extracting individual sprite frames...")
    all_extracted = {}

    for cat_name, discoveries in all_discoveries.items():
        config = CATEGORIES[cat_name]
        extracted = extract_individual_frames(discoveries, config)
        all_extracted[cat_name] = extracted
        print(f"  {cat_name}: {len(extracted)} individual frames extracted")

    print()

    # Step 3: Deduplicate
    print("Phase 3: Deduplicating frames...")
    for cat_name in all_extracted:
        all_extracted[cat_name] = deduplicate_frames(all_extracted[cat_name])

    print()

    # Step 4: Categorize and balance
    print("Phase 4: Categorizing and balancing...")
    category_frames = defaultdict(list)

    for cat_name, frames in all_extracted.items():
        for frame in frames:
            frame["category"] = cat_name
            category_frames[cat_name].append(frame)

    # Balance categories
    balanced = balance_categories(category_frames)

    # Collect all balanced frames
    all_balanced = []
    for category, frames in balanced.items():
        all_balanced.extend(frames)
        print(f"  {category}: {len(frames)} frames (capped)")

    print()

    # Step 5: Split into train/validation
    print("Phase 5: Splitting into train/validation sets...")
    # Simple 90/10 split, ensuring we don't split same character's frames
    import random
    random.seed(42)  # reproducible

    # Group by base character name for stratified split
    character_groups = defaultdict(list)
    for frame in all_balanced:
        # Extract character base name from output filename
        name = frame["output"].split('_')[0] if '_' in frame["output"] else frame["output"]
        character_groups[name].append(frame)

    train_set = []
    val_set = []

    for char_name, frames in character_groups.items():
        # Shuffle and split
        random.shuffle(frames)
        split_idx = int(len(frames) * 0.9)
        train_set.extend(frames[:split_idx])
        val_set.extend(frames[split_idx:])

    # Shuffle the final sets
    random.shuffle(train_set)
    random.shuffle(val_set)

    print(f"  Train set: {len(train_set)} frames")
    print(f"  Validation set: {len(val_set)} frames")

    print()

    # Step 6: Create output directory structure
    print("Phase 6: Creating output directory structure...")
    train_dir = OUTPUT_DIR / "train"
    val_dir = OUTPUT_DIR / "validation"

    # Clean and create directories
    if OUTPUT_DIR.exists():
        shutil.rmtree(OUTPUT_DIR)
    train_dir.mkdir(parents=True, exist_ok=True)
    val_dir.mkdir(parents=True, exist_ok=True)

    # Also create subdirectories for different categories if needed
    for cat_dir_name in ["character", "tile", "prop"]:
        (train_dir / cat_dir_name).mkdir(parents=True, exist_ok=True)
        (val_dir / cat_dir_name).mkdir(parents=True, exist_ok=True)

    print(f"  Output directory: {OUTPUT_DIR}")
    print(f"  Train directory: {train_dir}")
    print(f"  Validation directory: {val_dir}")
    print()

    # Step 7: Copy training images
    print("Phase 7: Copying training images...")
    train_manifest = []

    for frame in train_set:
        src = frame["path"]
        # Determine target subdirectory based on category
        cat_name = frame["category"]
        if cat_name in ["character", "tile", "prop"]:
            target_subdir = train_dir / cat_name
        else:
            target_subdir = train_dir

        # Determine output filename
        out_name = frame["output"]

        # Copy with progress
        try:
            shutil.copy2(str(src), str(target_subdir / out_name))
            train_manifest.append({
                "filename": out_name,
                "source": str(src),
                "category": cat_name,
                "direction": frame.get("direction", ""),
                "frame": frame.get("frame", ""),
            })
        except Exception as e:
            print(f"  ERROR copying {src} -> {target_subdir / out_name}: {e}")

    print(f"  Copied {len(train_manifest)} training images")

    print()

    # Step 8: Copy validation images
    print("Phase 8: Copying validation images...")
    val_manifest = []

    for frame in val_set:
        src = frame["path"]
        cat_name = frame["category"]
        if cat_name in ["character", "tile", "prop"]:
            target_subdir = val_dir / cat_name
        else:
            target_subdir = val_dir

        out_name = frame["output"]

        try:
            shutil.copy2(str(src), str(target_subdir / out_name))
            val_manifest.append({
                "filename": out_name,
                "source": str(src),
                "category": cat_name,
                "direction": frame.get("direction", ""),
                "frame": frame.get("frame", ""),
            })
        except Exception as e:
            print(f"  ERROR copying {src} -> {target_subdir / out_name}: {e}")

    print(f"  Copied {len(val_manifest)} validation images")

    print()

    # Step 9: Generate manifest CSV
    print("Phase 9: Generating manifest CSV...")
    all_manifest = train_manifest + val_manifest

    # Write manifest
    manifest_path = OUTPUT_DIR / "manifest.csv"
    with open(manifest_path, 'w', newline='') as f:
        f.write("filename,source_repo,category,direction,frame\n")
        for row in all_manifest:
            # Escape commas in paths if any
            filename = row["filename"].replace(',', '\\,')
            source = row["source"].replace(',', '\\,')
            direction = row["direction"].replace(',', '\\,') if row["direction"] else ""
            frame_val = row["frame"].replace(',', '\\,') if row["frame"] else ""
            f.write(f"{filename},{source},{category},{direction},{frame_val}\n")

    print(f"  Manifest written to: {manifest_path}")

    print()

    # Step 10: Generate palette PNG
    print("Phase 10: Generating palette reference...")
    # Collect all unique colors from extracted frames
    all_colors = set()

    for frame in all_balanced:
        try:
            img = Image.open(frame["path"])
            # Sample representative pixels
            w, h = img.size
            for y in range(0, h, max(1, h // 10)):
                for x in range(0, w, max(1, w // 10)):
                    r, g, b, a = img.getpixel((x, y))
                    if a > 0:  # only opaque pixels
                        all_colors.add((r, g, b))
        except Exception:
            pass

    # Create palette image
    palette_size = (256, 1)
    palette_img = Image.new("RGB", palette_size)

    for i, (r, g, b) in enumerate(sorted(all_colors)[:255]):
        palette_img.putpixel((i, 0), (r, g, b))

    palette_path = OUTPUT_DIR / "palette.png"
    palette_img.save(str(palette_path))

    print(f"  Palette image written to: {palette_path} ({len(all_colors)} unique colors sampled)")

    print()

    # Step 11: Generate report HTML
    print("Phase 11: Generating report HTML...")
    report = f"""
    <html>
    <head>
        <title>Duel Master Battle Sprite Dataset Report</title>
        <style>
            body {{ font-family: sans-serif; margin: 20px; background: #1a1a2e; color: #e0e0e0; }}
            h1 {{ color: #e94560; }}
            .section {{ margin-bottom: 20px; }}
            .stats {{ display: flex; gap: 20px; margin-bottom: 10px; }}
            .stat {{ background: #16213e; padding: 10px; border-radius: 4px; }}
            table {{ width: 100%; border-collapse: collapse; margin-top: 10px; }}
            th, td {{ border: 1px solid #444; padding: 4px; text-align: left; }}
            th {{ background: #16213e; }}
            .category {{ color: #e94560; }}
        </style>
    </head>
    <body>
        <h1>Duel Master Battle World Sprite Dataset</h1>
        <div class="stats">
            <div class="stat"><strong>Train Images</strong><br>{len(train_set)}</div>
            <div class="stat"><strong>Validation Images</strong><br>{len(val_set)}</div>
            <div class="stat"><strong>Total Categories</strong><br>{len(balanced)}</div>
        </div>

        <h2>Category Distribution</h2>
    """

    for category, frames in sorted(balanced.items()):
        report += f"<p class='category'>{category}: {len(frames)} frames</p>"

    report += """
        <h2>Sample Training Images</h2>
        <table>
            <tr><th>Filename</th><th>Category</th><th>Direction</th><th>Frame</th></tr>
    """

    # Show first 20 entries
    for entry in all_manifest[:20]:
        report += f"<tr><td>{entry['filename']}</td><td>{entry['category']}</td><td>{entry['direction'] or 'N/A'}</td><td>{entry['frame'] or 'N/A'}</td></tr>"

    report += """
        </table>
    </body>
    </html>
    """

    report_path = OUTPUT_DIR / "report.html"
    with open(report_path, 'w') as f:
        f.write(report)

    print(f"  Report written to: {report_path}")

    print()
    print("=" * 60)
    print("DATASET BUILD COMPLETE")
    print("=" * 60)
    print(f"\nOutput structure:")
    print(f"  {OUTPUT_DIR}/")
    print(f"  ├── train/          ({len(train_set)} images)")
    print(f"  ├── validation/     ({len(val_set)} images)")
    print(f"  ├── manifest.csv")
    print(f"  ├── palette.png    ({len(all_colors)} color samples)")
    print(f"  └── report.html")
    print()
    print(f"Next steps:")
    print(f"  1. Review the dataset with: open {report_path}")
    print(f"  2. Adjust category balances if needed")
    print(f"  3. Run caption generation or proceed to training")
    print(f"  4. Use process_generated_sprite.py to convert generated art")


if __name__ == "__main__":
    main()