#!/usr/bin/env python3
"""Generate local AnchorPy client bindings from the checked-in Jupiter IDL."""

from __future__ import annotations

import argparse
from pathlib import Path

from anchorpy.clientgen.accounts import gen_accounts
from anchorpy.clientgen.errors import gen_errors
from anchorpy.clientgen.instructions import gen_instructions
from anchorpy.clientgen.program_id import gen_program_id
from anchorpy.clientgen.types import gen_types
from anchorpy_core.idl import Idl

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_IDL = ROOT / "core" / "jupiter_perps" / "idl" / "jupiter_perps.json"
DEFAULT_OUT = ROOT / "core" / "jupiter_perps" / "client"
DEFAULT_PROGRAM_ID = "PERPHjGBqRHArX4DySjwM6UJHiR3sWAatqfdBS2qQJu"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate AnchorPy bindings for Jupiter Perps")
    parser.add_argument("--idl", type=Path, default=DEFAULT_IDL)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--program-id", type=str, default=DEFAULT_PROGRAM_ID)
    parser.add_argument("--pdas", action="store_true", default=True)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if not args.idl.exists():
        raise FileNotFoundError(f"IDL file not found: {args.idl}")

    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "__init__.py").touch(exist_ok=True)

    idl_obj = Idl.from_json(args.idl.read_text(encoding="utf-8-sig"))
    idl_program_id = idl_obj.metadata.get("address") if isinstance(idl_obj.metadata, dict) else None
    program_id = idl_program_id or args.program_id

    gen_program_id(program_id, args.out)
    gen_errors(idl_obj, args.out)
    gen_instructions(idl_obj, args.out, args.pdas)
    gen_types(idl_obj, args.out)
    gen_accounts(idl_obj, args.out)

    print(f"Generated AnchorPy bindings in: {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

