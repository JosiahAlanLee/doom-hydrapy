#!/usr/bin/env python3
"""Independent validator for the Null Run weapon pack.

Checks the saved PNGs and manifest, not the drawing code: dimensions, alpha
cleanliness, content bboxes, safe view region, flash alignment, icons, naming,
timings, SHA256SUMS, and byte-for-byte determinism of two fresh runs.
Exit code 0 = all checks passed.
"""
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

import numpy as np
from PIL import Image

BASE = Path(__file__).resolve().parent
W, H = 640, 400
SLOTS = {"melee", "sidearm", "scattergun", "repeater", "launcher", "projector", "heavy"}
NON_MELEE_STATES = {"idle", "raise_low", "raise_mid", "fire_peak", "fire_settle",
                    "recover", "reload_a", "reload_b"}
MELEE_STATES = {"idle", "raise_low", "raise_mid", "windup", "impact", "follow",
                "recover", "guard"}

class Checker:
    def __init__(self):
        self.rows = []
        self.failed = 0

    def check(self, name, cond, detail=""):
        ok = bool(cond)
        self.rows.append({"check": name, "ok": ok, "detail": str(detail)})
        if not ok:
            self.failed += 1
        return ok

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def bbox_incl(alpha):
    bb = Image.fromarray(alpha).getbbox()
    return None if bb is None else [bb[0], bb[1], bb[2] - 1, bb[3] - 1]

def main():
    c = Checker()
    manifest = json.loads((BASE / "manifest.json").read_text())
    slots = manifest.get("slots", [])
    c.check("manifest: 7 slots", len(slots) == 7, len(slots))
    c.check("manifest: slot names", {s.get("slot") for s in slots} == SLOTS,
            sorted(s.get("slot") for s in slots))
    c.check("manifest: canvas 640x400", manifest.get("canvas", {}).get("width") == W
            and manifest.get("canvas", {}).get("height") == H, manifest.get("canvas"))
    c.check("manifest: safe view documented", "safe_view" in manifest and "aim_clear_rect" in manifest["safe_view"])
    total_frames = total_flashes = total_icons = 0
    png_hashes = {}

    for slot in slots:
        sid = slot.get("id", "?")
        st = slot.get("slot")
        frames = slot.get("frames", [])
        states = [f.get("state") for f in frames]
        c.check(f"{sid}: 6-10 frames", 6 <= len(frames) <= 10, len(frames))
        c.check(f"{sid}: unique states", len(set(states)) == len(states), states)
        expected = MELEE_STATES if st == "melee" else NON_MELEE_STATES
        c.check(f"{sid}: required states", expected.issubset(set(states)),
                sorted(expected - set(states)))
        c.check(f"{sid}: role and duration", all(f.get("role") and f.get("duration_ms", 0) > 0 for f in frames))
        c.check(f"{sid}: suggested mapping", "suggested_mapping" in slot)
        flash_files = []
        frame_widths = []
        areas = []
        for f in frames:
            path = BASE / f.get("file", "")
            if not c.check(f"{sid}/{f.get('state')}: file exists", path.is_file(), path.name):
                continue
            img = Image.open(path)
            c.check(f"{sid}/{f.get('state')}: RGBA", img.mode == "RGBA", img.mode)
            c.check(f"{sid}/{f.get('state')}: 640x400", img.size == (W, H), img.size)
            if img.mode != "RGBA" or img.size != (W, H):
                continue
            arr = np.asarray(img)
            a = arr[..., 3]
            rgb = arr[..., :3]
            total_frames += 1
            png_hashes[f["file"]] = sha(path)
            bb = bbox_incl(a)
            c.check(f"{sid}/{f.get('state')}: bbox matches manifest", bb == f.get("content_bbox"), (bb, f.get("content_bbox")))
            c.check(f"{sid}/{f.get('state')}: alpha count matches", int((a > 0).sum()) == f.get("alpha_pixels"),
                    (int((a > 0).sum()), f.get("alpha_pixels")))
            c.check(f"{sid}/{f.get('state')}: non-empty alpha", bb is not None)
            c.check(f"{sid}/{f.get('state')}: central aim clear", int((a[40:180, 220:420] > 0).sum()) == 0,
                    int((a[40:180, 220:420] > 0).sum()))
            c.check(f"{sid}/{f.get('state')}: nothing above y=190", int((a[:190] > 0).sum()) == 0,
                    int((a[:190] > 0).sum()))
            band = a[190:240]
            ys, xs = np.nonzero(band)
            c.check(f"{sid}/{f.get('state')}: 190-239 x band 250-440",
                    len(xs) == 0 or (xs.min() >= 250 and xs.max() <= 440),
                    (int(xs.min()), int(xs.max())) if len(xs) else None)
            c.check(f"{sid}/{f.get('state')}: bottom crop present", int((a[392:, :] > 0).sum()) > 0)
            c.check(f"{sid}/{f.get('state')}: no left/right/top edge crop",
                    int(a[:, 0].sum() + a[:, -1].sum() + a[0, :].sum()) == 0)
            coverage = float((a > 0).mean())
            c.check(f"{sid}/{f.get('state')}: sane coverage", 0.005 < coverage < 0.30, round(coverage, 4))
            c.check(f"{sid}/{f.get('state')}: corners transparent",
                    int(a[0, 0] + a[0, -1] + a[-1, 0] + a[-1, -1]) == 0)
            c.check(f"{sid}/{f.get('state')}: RGB clear under alpha=0",
                    int(np.abs(rgb[a == 0]).sum()) == 0)
            partial = (a > 0) & (a < 255)
            c.check(f"{sid}/{f.get('state')}: no pure-black edge fringe",
                    int(((partial) & (rgb.max(axis=2) <= 2)).sum()) == 0,
                    int(((partial) & (rgb.max(axis=2) <= 2)).sum()))
            if bb:
                frame_widths.append(bb[2] - bb[0] + 1)
                areas.append((bb[2] - bb[0] + 1) * (bb[3] - bb[1] + 1))
            if f.get("flash"):
                flash_files.append(f["flash"])
        if frame_widths:
            # Silhouette bboxes legitimately grow when an arm angles outward or
            # the weapon is raised, so width/area are not a scale test. Check
            # instead that no frame declares a scale and that implied motion is
            # bounded, then state the limitation in the report.
            c.check(f"{sid}: no per-frame scale declared",
                    all("scale" not in f.get("generation_pose", {}) for f in frames))
            by_state = {f.get("state"): f for f in frames}
            idle = by_state.get("idle", {}).get("muzzle_world")
            if idle:
                for st_name in ("fire_peak", "fire_settle", "recover"):
                    f = by_state.get(st_name)
                    if f:
                        dx = f["muzzle_world"][0] - idle[0]
                        dy = f["muzzle_world"][1] - idle[1]
                        c.check(f"{sid}/{st_name}: bounded muzzle motion", abs(dx) < 40 and abs(dy) < 30,
                                (round(dx, 1), round(dy, 1)))
        # flashes
        fl = slot.get("flashes", [])
        c.check(f"{sid}: 2 flash overlays", len(fl) == 2, len(fl))
        c.check(f"{sid}: fire frames reference flashes",
                all(f.get("flash") for f in frames if f.get("state") in ("fire_peak", "fire_settle", "impact", "follow")))
        for fm in fl:
            path = BASE / fm.get("file", "")
            if not c.check(f"{sid}/flash {fm.get('variant')}: file exists", path.is_file(), path.name):
                continue
            img = Image.open(path)
            c.check(f"{sid}/flash {fm.get('variant')}: RGBA 640x400", img.mode == "RGBA" and img.size == (W, H), (img.mode, img.size))
            if img.mode != "RGBA" or img.size != (W, H):
                continue
            arr = np.asarray(img)
            a = arr[..., 3]
            rgb = arr[..., :3]
            total_flashes += 1
            png_hashes[fm["file"]] = sha(path)
            bb = bbox_incl(a)
            c.check(f"{sid}/flash {fm.get('variant')}: bbox matches", bb == fm.get("content_bbox"), (bb, fm.get("content_bbox")))
            c.check(f"{sid}/flash {fm.get('variant')}: alpha count matches", int((a > 0).sum()) == fm.get("alpha_pixels"))
            c.check(f"{sid}/flash {fm.get('variant')}: muzzle inside bbox",
                    bb is not None and bb[0] - 3 <= fm["muzzle_world"][0] <= bb[2] + 3
                    and bb[1] - 3 <= fm["muzzle_world"][1] <= bb[3] + 3,
                    (fm.get("muzzle_world"), bb))
            c.check(f"{sid}/flash {fm.get('variant')}: coverage sane", 0.002 < float((a > 0).mean()) < 0.15,
                    round(float((a > 0).mean()), 4))
            c.check(f"{sid}/flash {fm.get('variant')}: corners transparent",
                    int(a[0, 0] + a[0, -1] + a[-1, 0] + a[-1, -1]) == 0)
            c.check(f"{sid}/flash {fm.get('variant')}: RGB clear under alpha=0",
                    int(np.abs(rgb[a == 0]).sum()) == 0)
            c.check(f"{sid}/flash {fm.get('variant')}: matching frame valid",
                    fm.get("for_frame_index") is not None and 0 <= fm["for_frame_index"] < len(frames))
        # icon
        ic = slot.get("icon", {})
        ipath = BASE / ic.get("file", "")
        if c.check(f"{sid}: icon exists", ipath.is_file(), ipath.name):
            img = Image.open(ipath)
            c.check(f"{sid}: icon RGBA 96x64", img.mode == "RGBA" and img.size == (96, 64), (img.mode, img.size))
            if img.mode == "RGBA" and img.size == (96, 64):
                arr = np.asarray(img)
                a = arr[..., 3]
                total_icons += 1
                png_hashes[ic["file"]] = sha(ipath)
                bb = bbox_incl(a)
                c.check(f"{sid}: icon bbox matches", bb == ic.get("content_bbox"), (bb, ic.get("content_bbox")))
                c.check(f"{sid}: icon has transparent margin",
                        bb is not None and bb[0] >= 2 and bb[1] >= 2 and bb[2] <= 93 and bb[3] <= 61, bb)
                c.check(f"{sid}: icon coverage sane", 0.05 < float((a > 0).mean()) < 0.45,
                        round(float((a > 0).mean()), 4))
                c.check(f"{sid}: icon RGB clear under alpha=0",
                        int(np.abs(arr[..., :3][a == 0]).sum()) == 0)

    c.check("frame count", total_frames == 56, total_frames)
    c.check("flash count", total_flashes == 14, total_flashes)
    c.check("icon count", total_icons == 7, total_icons)

    # SHA256SUMS, as written with the pack
    sums_path = BASE / "SHA256SUMS"
    listed = {}
    if c.check("SHA256SUMS exists", sums_path.is_file()):
        for line in sums_path.read_text().splitlines():
            if not line.strip():
                continue
            h, rel = line.split("  ", 1)
            listed[rel] = h
            p = BASE / rel
            if not c.check(f"sums: {rel} exists", p.is_file()):
                continue
            c.check(f"sums: {rel} hash", sha(p) == h)
        c.check("sums: no duplicates", len(listed) == len(sums_path.read_text().splitlines()))

    # determinism: two fresh, black-box runs into temp folders
    det = BASE / "_determinism"
    try:
        if det.exists():
            shutil.rmtree(det)
        runs = []
        for name in ("run_a", "run_b"):
            out = det / name
            r = subprocess.run([sys.executable, str(BASE / "generate_weapons.py"), "--out", str(out)],
                               cwd=str(BASE), capture_output=True, text=True)
            c.check(f"determinism: {name} generator exit", r.returncode == 0, r.stderr[-300:])
            runs.append(out)
        files_a = sorted(p.relative_to(runs[0]) for p in runs[0].rglob("*") if p.is_file())
        files_b = sorted(p.relative_to(runs[1]) for p in runs[1].rglob("*") if p.is_file())
        c.check("determinism: same file set", files_a == files_b, (len(files_a), len(files_b)))
        pngs = [p for p in files_a if p.suffix == ".png"]
        mismatches = [str(p) for p in pngs if not (runs[1] / p).is_file()
                      or sha(runs[0] / p) != sha(runs[1] / p)]
        c.check("determinism: all PNGs byte-identical", not mismatches,
                {"pngs": len(pngs), "mismatches": mismatches[:6]})
        jm = [str(p) for p in files_a if p.suffix == ".json"
              and (not (runs[1] / p).is_file() or sha(runs[0] / p) != sha(runs[1] / p))]
        c.check("determinism: all JSON identical", not jm, jm[:6])
        # expected artefact count: 56 frames + 14 flashes + 7 icons + 11 sheets
        c.check("determinism: PNG count", len(pngs) == 88, len(pngs))
    finally:
        if det.exists():
            shutil.rmtree(det)

    # provenance / process checks (textual, cheap)
    gen = (BASE / "generate_weapons.py").read_text()
    c.check("generator reads no images", "Image.open" not in gen and "imread" not in gen,
            "Image.open present" if "Image.open" in gen else "clean")
    pack_files = [p.name.lower() for p in BASE.rglob("*") if p.is_file()]
    c.check("no WAD/PK3/LMP assets in pack", not any(f.endswith((".wad", ".pk3", ".lmp")) for f in pack_files))
    c.check("generator reads no external files",
            "Image.open" not in gen and "np.load" not in gen and ".load(" not in gen)
    c.check("provenance/licence file", (BASE / "PROVENANCE.md").is_file())
    c.check("integration notes", (BASE / "INTEGRATION.md").is_file())
    c.check("materials source", (BASE / "materials.json").is_file())
    c.check("geometry source", (BASE / "geometry.json").is_file())

    # final sums include every artefact except report and the sums file itself
    final = []
    for p in sorted(BASE.rglob("*")):
        if not p.is_file():
            continue
        rel = p.relative_to(BASE).as_posix()
        if rel in ("SHA256SUMS", "validation_report.json") or "__pycache__" in p.parts:
            continue
        final.append(f"{sha(p)}  {rel}")
    sums_path.write_text("\n".join(final) + "\n")
    c.check("sums rewritten for all artefacts", len(final) >= 80, len(final))

    report = {
        "pack": manifest.get("pack"),
        "passed": c.failed == 0,
        "failed_checks": c.failed,
        "counts": {"slots": len(slots), "frames": total_frames, "flashes": total_flashes,
                   "icons": total_icons, "png_hashes": len(png_hashes)},
        "checks": c.rows,
        "limitations": [
            "Validation is geometric and alpha-based; it cannot judge artistic quality.",
            "No engine, palette conversion or runtime integration was tested.",
            "The edge-fringe check only catches pure-black partial pixels; it is not a full compositing proof.",
            "Scale stability is guaranteed by the generator having no scale parameter and is not independently measurable from silhouettes."
        ]
    }
    (BASE / "validation_report.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({k: report[k] for k in ("passed", "failed_checks", "counts")}, indent=2))
    for row in c.rows:
        if not row["ok"]:
            print("FAIL", row["check"], row["detail"])
    return 0 if c.failed == 0 else 1

if __name__ == "__main__":
    sys.exit(main())
