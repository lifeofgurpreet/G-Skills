#!/usr/bin/env python3
"""Enforce the selected Codex model at a launcher process boundary.

This is deliberately a small argv adapter. It never inspects prompts, tokens,
URLs, or conversation data, and it stops parsing after the conventional ``--``
prompt separator.
"""
import os
import re
import sys

DEFAULT_MODEL = "gpt-6.1-sol"
DEFAULT_EFFORT = "medium"
EFFORTS = {"low", "medium", "high", "xhigh", "max", "ultra"}


def policy():
    model = os.environ.get("RESET_BOOST_MODEL", DEFAULT_MODEL)
    effort = os.environ.get("RESET_BOOST_REASONING_EFFORT", DEFAULT_EFFORT)
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:/@+-]*", model):
        model = DEFAULT_MODEL
    if effort not in EFFORTS:
        effort = DEFAULT_EFFORT
    return model, effort


def rewrite(argv):
    """Return provider argv with model and effort pinned before ``--``."""
    model, effort = policy()
    out = []
    saw_model = False
    saw_effort = False
    i = 0
    while i < len(argv):
        arg = argv[i]
        if arg == "--":
            out.extend(argv[i:])
            break
        if arg in ("-m", "--model"):
            out.extend((arg, model))
            saw_model = True
            i += 2 if i + 1 < len(argv) else 1
            continue
        if arg.startswith("--model="):
            out.append("--model=" + model)
            saw_model = True
            i += 1
            continue
        if arg in ("-c", "--config"):
            if i + 1 >= len(argv):
                # A dangling config flag would shift the policy argument into
                # the provider's parser. Normalize it to a valid effort setting.
                out.extend((arg, "model_reasoning_effort=" + effort))
                saw_effort = True
                i += 1
                continue
            value = argv[i + 1]
            key, _, _ = value.partition("=")
            if key == "model":
                out.extend((arg, "model=" + model))
                saw_model = True
                i += 2
                continue
            if key == "model_reasoning_effort":
                out.extend((arg, "model_reasoning_effort=" + effort))
                saw_effort = True
                i += 2
                continue
            out.extend((arg, value))
            i += 2
            continue
        if arg.startswith("--config="):
            value = arg[len("--config="):]
            key, _, _ = value.partition("=")
            if key == "model":
                out.append("--config=model=" + model)
                saw_model = True
                i += 1
                continue
            if key == "model_reasoning_effort":
                out.append("--config=model_reasoning_effort=" + effort)
                saw_effort = True
                i += 1
                continue
        if arg.startswith("model_reasoning_effort="):
            out.append("model_reasoning_effort=" + effort)
            saw_effort = True
            i += 1
            continue
        out.append(arg)
        i += 1
    else:
        if not saw_model:
            out.extend(("-m", model))
        if not saw_effort:
            out.extend(("-c", "model_reasoning_effort=" + effort))
        return out
    # ``--`` was copied above; append policy flags before it, preserving the
    # user's prompt and every argument after the separator byte-for-byte.
    marker = out.index("--")
    prefix, suffix = out[:marker], out[marker:]
    if not saw_model:
        prefix.extend(("-m", model))
    if not saw_effort:
        prefix.extend(("-c", "model_reasoning_effort=" + effort))
    return prefix + suffix


if __name__ == "__main__":
    if len(sys.argv) < 3 or sys.argv[1] != "--":
        raise SystemExit("usage: model-policy-guard.py -- command [args ...]")
    command = sys.argv[2]
    # execvp requires argv[0] explicitly. Omitting it silently shifts the
    # provider's arguments and was the reason the first guard was incomplete.
    os.execvp(command, [command, *rewrite(sys.argv[3:])])
