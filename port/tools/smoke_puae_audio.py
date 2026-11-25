#!/usr/bin/env python3
"""Bounded per-channel PC/PUAE PCM parity from the shared gameplay entry.

Paula and the native mixer advance their DMA pointers continuously, while the
libretro oracle delivers PCM in host callbacks.  A single global lag therefore
produces false divergence when a streamed buffer loops.  World-5 (level 49) is
isolated per channel and aligned in short bounded windows; other levels retain
the established whole-mix gate.  Content/gain parity is required without
demanding identical callback latency.
"""
from __future__ import annotations

import argparse
import array
import math
import os
from pathlib import Path
import re
import shutil
import statistics
import subprocess

PORT = Path(__file__).resolve().parents[1]
ROOT = PORT.parent
HARNESS = PORT / "build" / "benefactor-harness"
PC_RATE = 44100
PUAE_RATE = 44100


def read_mono(path: Path, rate: int) -> list[float]:
    data = array.array("h")
    data.frombytes(path.read_bytes())
    if rate not in (22050, 44100):
        raise ValueError(f"unsupported rate {rate}")
    return [(data[2 * i] + data[2 * i + 1]) / 2 for i in range(len(data) // 2)]


def rms(values: list[float]) -> float:
    return math.sqrt(sum(v * v for v in values) / len(values)) if values else 0.0


def fit(pc: list[float], puae: list[float], start: int, end: int, lag: int):
    lo = max(start, lag)
    hi = min(end, len(puae) + lag)
    if hi - lo < 100:
        return -1.0, 0.0
    pp = uu = xy = 0.0
    for i in range(lo, hi):
        x = pc[i]
        y = puae[i - lag]
        pp += x * x
        uu += y * y
        xy += x * y
    if pp <= 1e-9 or uu <= 1e-9:
        return -1.0, 0.0
    return xy / math.sqrt(pp * uu), xy / pp


def best_lag(pc: list[float], puae: list[float], start: int, end: int,
             low: int = -2000, high: int = 200):
    """Coarse-to-fine local alignment; 2-sample coarse steps avoid periodic false peaks."""
    best = (-1.0, 0, 0.0)
    for lag in range(low, high + 1, 2):
        corr, gain = fit(pc, puae, start, end, lag)
        if corr > best[0]:
            best = (corr, lag, gain)
    center = best[1]
    for lag in range(center - 3, center + 4):
        corr, gain = fit(pc, puae, start, end, lag)
        if corr > best[0]:
            best = (corr, lag, gain)
    return best


def capture(level: int, channel: int | None):
    if not (PORT / "logs" / "puae_sync.state").is_file():
        raise SystemExit("missing frozen PUAE state; run tools/smoke_puae_oracle.py first")
    env = os.environ.copy()
    env["BENEFACTOR_REFREEZE"] = "0"
    if channel is not None:
        env["AUDCH_ONLY"] = str(channel)
        if level == 49:
            env["BENEFACTOR_AUDIO_SYNC_WORK"] = "1"
    else:
        env.pop("AUDCH_ONLY", None)
        env.pop("BENEFACTOR_AUDIO_SYNC_WORK", None)
    suffix = "mixed" if channel is None else f"ch{channel}"
    log_path = ROOT / "analysis" / f"puae-audio-parity-level{level}-{suffix}.log"
    commands = "\n".join([
        "pumenu", "fire 1", "pu 6", "fire 0", "purunto 577000 2000",
        f"mwp 20 {level:02X} w", "mpu 20 1 w", "pufrompc 0 100",
        "syncbeam", "both 600", "fire 1", "both 8", "fire 0", "both 480",
        "syncmusic", f"pumute {(1 << channel) if channel is not None else 15}",
        "acap on", "both 60", "acap off", "q", ""
    ])
    proc = subprocess.run([
        str(HARNESS), "--level", str(level), "Disk.1", "Disk.2", "Disk.3",
        "--kick", "kickstart", "--whdload",
        str(PORT / "oracle-whdload" / "Benefactor")
    ], cwd=PORT, env=env, input=commands, text=True, stdout=subprocess.PIPE,
       stderr=subprocess.STDOUT, timeout=300, check=False)
    log_path.write_text(proc.stdout)
    if proc.returncode != 0:
        raise SystemExit(f"harness exited {proc.returncode}; see {log_path}")
    if not re.search(r"audio capture=1", proc.stdout) or not re.search(r"audio capture=0", proc.stdout):
        raise SystemExit(f"audio capture window did not run; see {log_path}")

    pc_path = ROOT / "analysis" / f"puae-audio-level{level}-{suffix}-pc.raw"
    puae_path = ROOT / "analysis" / f"puae-audio-level{level}-{suffix}-puae.raw"
    shutil.copyfile(PORT / "logs" / "audio_pc.raw", pc_path)
    shutil.copyfile(PORT / "logs" / "audio_puae.raw", puae_path)
    return read_mono(pc_path, PC_RATE), read_mono(puae_path, PUAE_RATE)


def global_lag(pc: list[float], puae: list[float], n: int) -> int:
    block = 20
    pb = [sum(pc[i:i + block]) / block for i in range(0, n, block)]
    ub = [sum(puae[i:i + block]) / block for i in range(0, n, block)]
    nb = min(len(pb), len(ub))
    best = (-1.0, 0)
    for lag in range(-300, 301):
        lo = max(0, lag)
        hi = min(nb, nb + lag)
        if hi - lo < 5:
            continue
        pp = uu = xy = 0.0
        for i in range(lo, hi):
            x = pb[i]
            y = ub[i - lag]
            pp += x * x
            uu += y * y
            xy += x * y
        if pp <= 1e-9 or uu <= 1e-9:
            continue
        corr = xy / math.sqrt(pp * uu)
        if corr > best[0]:
            best = (corr, lag * block)
    center = best[1]
    refined = (-1.0, center)
    for lag in range(center - 30, center + 31):
        corr, _ = fit(pc, puae, 0, n, lag)
        if corr > refined[0]:
            refined = (corr, lag)
    return refined[1]


def analyze(level: int, channel: int, pc: list[float], puae: list[float]) -> bool:
    n = min(len(pc), len(puae))
    if n < PC_RATE // 2:
        raise SystemExit(f"level {level} ch{channel}: capture too short: {n} frames")
    pc_rms = rms(pc[:n])
    puae_rms = rms(puae[:n])
    if pc_rms < 100 and puae_rms < 100:
        print(f"level {level} ch{channel}: silent in both cores (skip)")
        return True
    if pc_rms < 100 or puae_rms < 100:
        raise SystemExit(
            f"level {level} ch{channel}: one-sided silence PC={pc_rms:.1f} PUAE={puae_rms:.1f}"
        )

    window = PC_RATE // 50
    center = global_lag(pc, puae, n)
    metrics: list[tuple[float, int, float]] = []
    for start in range(0, n - window + 1, window):
        if rms(pc[start:start + window]) < 100 or rms(puae[start:start + window]) < 100:
            continue
        metrics.append(best_lag(pc, puae, start, start + window,
                                center - 600, center + 600))
    if len(metrics) < 20:
        raise SystemExit(f"level {level} ch{channel}: too few audible windows: {len(metrics)}")

    corrs = [m[0] for m in metrics]
    gains = [m[2] for m in metrics]
    median_corr = statistics.median(corrs)
    median_gain = statistics.median(gains)
    good = sum(c >= 0.80 for c in corrs)
    ratio = pc_rms / puae_rms
    print(
        f"level {level} ch{channel}: frames={n} audible={len(metrics)} "
        f"corr_median={median_corr:.4f} good={good}/{len(metrics)} "
        f"gain_median={median_gain:.4f} rms_ratio={ratio:.4f}"
    )
    if median_corr < 0.85 or good < math.ceil(0.85 * len(metrics)):
        raise SystemExit(f"level {level} ch{channel}: aligned PCM content diverges")
    if not 0.80 <= median_gain <= 1.20:
        raise SystemExit(f"level {level} ch{channel}: aligned PCM gain differs: {median_gain:.4f}")
    if not 0.75 <= ratio <= 1.25:
        raise SystemExit(f"level {level} ch{channel}: PCM RMS differs: {ratio:.4f}")
    return True


def analyze_mixed(level: int, pc: list[float], puae: list[float]) -> bool:
    """Retain the established whole-mix gate for non-world-5 levels."""
    n = min(len(pc), len(puae))
    if n < PC_RATE // 2:
        raise SystemExit(f"level {level}: capture too short: {n} frames")
    pc_rms = rms(pc[:n])
    puae_rms = rms(puae[:n])
    if pc_rms < 100 or puae_rms < 100:
        raise SystemExit(f"level {level}: silent capture PC={pc_rms:.1f} PUAE={puae_rms:.1f}")
    center = global_lag(pc, puae, n)
    window = PC_RATE // 10
    metrics = []
    for start in range(0, n - window + 1, window):
        metrics.append(best_lag(pc, puae, start, start + window,
                                center - 300, center + 300))
    corrs = [m[0] for m in metrics]
    gains = [m[2] for m in metrics]
    median_corr = statistics.median(corrs)
    median_gain = statistics.median(gains)
    good = sum(c >= 0.80 for c in corrs)
    ratio = pc_rms / puae_rms
    print(
        f"level {level} mixed: frames={n} lag={center} "
        f"corr_median={median_corr:.4f} good={good}/{len(metrics)} "
        f"gain_median={median_gain:.4f} rms_ratio={ratio:.4f}"
    )
    if median_corr < 0.85 or good < len(metrics) - 4:
        raise SystemExit(f"level {level}: mixed PCM content diverges after alignment")
    if not 0.80 <= median_gain <= 1.20:
        raise SystemExit(f"level {level}: mixed PCM gain differs: {median_gain:.4f}")
    if not 0.75 <= ratio <= 1.25:
        raise SystemExit(f"level {level}: mixed PCM RMS differs: {ratio:.4f}")
    return True


def main(level: int = 1) -> int:
    if level == 49:
        for channel in range(4):
            pc, puae = capture(level, channel)
            analyze(level, channel, pc, puae)
        print("PASS bounded per-channel audio parity (level 49)")
    else:
        pc, puae = capture(level, None)
        analyze_mixed(level, pc, puae)
        print(f"PASS bounded mixed audio parity (level {level})")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--level", type=int, default=1)
    args = parser.parse_args()
    if not 1 <= args.level <= 60:
        raise SystemExit("level must be 1..60")
    raise SystemExit(main(args.level))
