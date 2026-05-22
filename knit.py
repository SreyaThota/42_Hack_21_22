import argparse
import json
import re
import sys
from typing import Any

ERROR_ORDER = [
    "MISSING_PATTERN", "MALFORMED_PATTERN", "DUPLICATE_PATTERN",
    "MISSING_CAST_ON", "MALFORMED_CAST_ON", "DUPLICATE_CAST_ON",
    "CAST_ON_OUT_OF_ORDER",
    "UNKNOWN_STATEMENT",
    "MALFORMED_ROW", "DUPLICATE_ROW", "OUT_OF_ORDER_ROW",
    "UNKNOWN_STITCH",
    "STITCH_UNDERFLOW", "STITCH_OVERFLOW",
    "MALFORMED_REPEAT", "INVALID_REPEAT_COUNT", "INVALID_REPEAT_RANGE",
    "MALFORMED_BIND_OFF", "DUPLICATE_BIND_OFF", "BIND_OFF_OUT_OF_ORDER",
]

VALID_KEYWORDS = {"pattern", "cast_on", "row", "repeat", "bind_off"}
STITCH_CONSUME_PRODUCE = {
    "k": (1, 1),
    "p": (1, 1),
    "yo": (0, 1),
    "k2tog": (2, 1),
    "ssk": (2, 1),
    "inc": (1, 2),
    "dec": (2, 1),
}


def strip_comments(line: str) -> str:
    result = []
    in_quotes = False
    for ch in line:
        if ch == '"':
            in_quotes = not in_quotes
        if ch == '#' and not in_quotes:
            break
        result.append(ch)
    return "".join(result).rstrip()


def has_token_boundary(line: str, keyword: str, pos: int) -> bool:
    end = pos + len(keyword)
    if end < len(line) and line[end] not in ' \t':
        return False
    if pos > 0 and line[pos - 1] not in ' \t':
        return False
    return True


def find_keyword(line: str, start: int = 0) -> tuple[str | None, int, int]:
    best_kw = None
    best_pos = len(line) + 1
    for kw in VALID_KEYWORDS:
        idx = line.find(kw, start)
        while idx != -1:
            if has_token_boundary(line, kw, idx):
                if idx < best_pos:
                    best_kw = kw
                    best_pos = idx
                break
            idx = line.find(kw, idx + 1)
    if best_kw is None:
        return None, -1, -1
    return best_kw, best_pos, best_pos + len(best_kw)


def parse_instructions(text: str, line_num: int, row_num: int | None) -> tuple[list[dict], list[dict]]:
    instructions: list[dict] = []
    errors: list[dict] = []
    remaining = text.strip()
    if not remaining:
        return instructions, errors
    bracket_depth = 0
    items: list[str] = []
    current: list[str] = []
    i = 0
    while i < len(remaining):
        ch = remaining[i]
        if ch == '[':
            bracket_depth += 1
            current.append(ch)
        elif ch == ']':
            bracket_depth -= 1
            current.append(ch)
        elif ch == ',' and bracket_depth == 0:
            items.append("".join(current).strip())
            current = []
        else:
            current.append(ch)
        i += 1
    items.append("".join(current).strip())

    malformed = False
    for idx, item in enumerate(items):
        if not item:
            err = {"type": "error", "code": "MALFORMED_ROW", "message": "Empty instruction item.", "line": line_num, "row": row_num}
            if err not in errors:
                errors.append(err)
            malformed = True
            continue
        bracket_match = re.match(r'^\[(.+)\]\s+x(\d+)$', item)
        if item.startswith('[') and not bracket_match:
            err = {"type": "error", "code": "MALFORMED_ROW", "message": f"Malformed bracket syntax: {item}.", "line": line_num, "row": row_num}
            if err not in errors:
                errors.append(err)
            malformed = True
            continue
        if bracket_match:
            inner = bracket_match.group(1).strip()
            count = int(bracket_match.group(2))
            if count < 1:
                err = {"type": "error", "code": "MALFORMED_ROW", "message": "Invalid bracket repeat count.", "line": line_num, "row": row_num}
                if err not in errors:
                    errors.append(err)
                malformed = True
                continue
            inner_items, inner_errors = parse_instructions(inner, line_num, row_num)
            errors.extend(inner_errors)
            if malformed:
                continue
            for _ in range(count):
                for inst in inner_items:
                    instructions.append(dict(inst))
            continue
        fixed_stitches = {"yo", "k2tog", "ssk", "inc", "dec"}
        if item in fixed_stitches:
            instructions.append({"stitch": item, "count": 1})
            continue
        if ' ' in item and ',' not in item and not re.match(r'^[kp]\d+$', item):
            err = {"type": "error", "code": "MALFORMED_ROW", "message": f"Malformed instruction: {item}.", "line": line_num, "row": row_num}
            if err not in errors:
                errors.append(err)
            malformed = True
            continue
        stitch_match = re.match(r'^([kp])(\d+)$', item)
        if stitch_match:
            stitch_name = stitch_match.group(1)
            count = int(stitch_match.group(2))
            if count >= 1:
                instructions.append({"stitch": stitch_name, "count": count})
            else:
                err = {"type": "error", "code": "UNKNOWN_STITCH", "message": f"Unknown stitch: {item}.", "line": line_num, "row": row_num}
                if err not in errors:
                    errors.append(err)
        else:
            err = {"type": "error", "code": "UNKNOWN_STITCH", "message": f"Unknown stitch: {item}.", "line": line_num, "row": row_num}
            if err not in errors:
                errors.append(err)
    return instructions, errors


def make_error(code: str, message: str, line: int | None, row: int | None) -> dict:
    return {"type": "error", "code": code, "message": message, "line": line, "row": row}


def sort_errors(errors: list[dict]) -> list[dict]:
    def sort_key(e: dict):
        ln = e["line"] if e["line"] is not None else 999999
        code_idx = ERROR_ORDER.index(e["code"]) if e["code"] in ERROR_ORDER else 999
        return (ln, code_idx)
    errors.sort(key=sort_key)
    return errors


def compile_file(filepath: str) -> str:
    with open(filepath, "r") as f:
        raw_lines = f.readlines()

    pattern_name: str | None = None
    cast_on: int | None = None
    has_valid_bind_off = False
    valid_bind_off_count = 0
    rows: dict[int, dict] = {}
    row_order: list[int] = []
    repeat_statements: list[dict] = []
    source_order: list[dict] = []
    errors: list[dict] = []
    max_claimed_row = 0
    has_any_row = False
    has_valid_bind_off_line = False

    line_num = 0
    i = 0
    while i < len(raw_lines):
        raw = raw_lines[i]
        line_num += 1
        stripped = strip_comments(raw.rstrip('\n\r'))
        if not stripped.strip():
            i += 1
            continue

        kw, kw_start, kw_end = find_keyword(stripped)
        if kw is None:
            errors.append(make_error("UNKNOWN_STATEMENT", f"Unknown statement on line {line_num}.", line_num, None))
            i += 1
            continue

        after_kw = stripped[kw_end:].strip()

        if kw not in ("bind_off", "row", "repeat") and has_valid_bind_off and has_valid_bind_off_line:
            errors.append(make_error("BIND_OFF_OUT_OF_ORDER", f"Statement after bind_off on line {line_num}.", line_num, None))

        if kw == "pattern":
            pattern_match = re.match(r'^"([^"]*)"\s*$', after_kw)
            if pattern_match:
                name = pattern_match.group(1)
                if pattern_name is not None:
                    errors.append(make_error("DUPLICATE_PATTERN", f"Duplicate pattern on line {line_num}.", line_num, None))
                    pattern_name = None
                else:
                    pattern_name = name
            else:
                errors.append(make_error("MALFORMED_PATTERN", f"Malformed pattern on line {line_num}.", line_num, None))
                if pattern_name is None:
                    pattern_name = None

        elif kw == "cast_on":
            if has_any_row:
                co_match = re.match(r'^(\d+)\s*$', after_kw)
                if co_match:
                    val = int(co_match.group(1))
                    if val < 1:
                        errors.append(make_error("MALFORMED_CAST_ON", f"Malformed cast_on on line {line_num}.", line_num, None))
                        if cast_on is not None:
                            pass
                    else:
                        errors.append(make_error("CAST_ON_OUT_OF_ORDER", f"cast_on after rows on line {line_num}.", line_num, None))
                        if cast_on is None:
                            cast_on = val
                        else:
                            errors.append(make_error("DUPLICATE_CAST_ON", f"Duplicate cast_on on line {line_num}.", line_num, None))
                            cast_on = None
                else:
                    errors.append(make_error("MALFORMED_CAST_ON", f"Malformed cast_on on line {line_num}.", line_num, None))
                    errors.append(make_error("CAST_ON_OUT_OF_ORDER", f"cast_on after rows on line {line_num}.", line_num, None))
            else:
                co_match = re.match(r'^(\d+)\s*$', after_kw)
                if co_match:
                    val = int(co_match.group(1))
                    if val < 1:
                        errors.append(make_error("MALFORMED_CAST_ON", f"Malformed cast_on on line {line_num}.", line_num, None))
                    else:
                        if cast_on is not None:
                            errors.append(make_error("DUPLICATE_CAST_ON", f"Duplicate cast_on on line {line_num}.", line_num, None))
                            cast_on = None
                        else:
                            cast_on = val
                else:
                    errors.append(make_error("MALFORMED_CAST_ON", f"Malformed cast_on on line {line_num}.", line_num, None))

        elif kw == "row":
            has_any_row = True
            row_match = re.match(r'^(\d+):\s*(.*)', after_kw)
            if not row_match:
                errors.append(make_error("MALFORMED_ROW", f"Malformed row on line {line_num}.", line_num, None))
                i += 1
                continue
            row_num_str = row_match.group(1)
            row_num = int(row_num_str)
            if row_num < 1:
                errors.append(make_error("MALFORMED_ROW", f"Malformed row number on line {line_num}.", line_num, None))
                i += 1
                continue
            instr_text = row_match.group(2).strip()
            if not instr_text:
                errors.append(make_error("MALFORMED_ROW", f"Row has no instructions on line {line_num}.", line_num, row_num))
                if row_num not in rows:
                    rows[row_num] = {"line": line_num, "state": "claimed", "instructions": [], "raw_instructions": ""}
                    row_order.append(row_num)
                i += 1
                continue
            instrs, instr_errors = parse_instructions(instr_text, line_num, row_num)
            errors.extend(instr_errors)

            has_fatal = any(e["code"] in ("MALFORMED_ROW", "UNKNOWN_STITCH") for e in instr_errors)

            if has_valid_bind_off and has_valid_bind_off_line:
                errors.append(make_error("BIND_OFF_OUT_OF_ORDER", f"Row after bind_off on line {line_num}.", line_num, row_num))

            if row_num in rows:
                errors.append(make_error("DUPLICATE_ROW", f"Duplicate row {row_num} on line {line_num}.", line_num, row_num))
            elif row_num < max_claimed_row:
                errors.append(make_error("OUT_OF_ORDER_ROW", f"Out of order row {row_num} on line {line_num}.", line_num, row_num))
                row_data = {"line": line_num, "state": "out_of_order", "instructions": [], "raw_instructions": ""}
                rows[row_num] = row_data
            else:
                if has_fatal or (has_valid_bind_off and has_valid_bind_off_line):
                    state = "excluded"
                else:
                    state = "valid"
                row_data = {"line": line_num, "state": state, "instructions": instrs if not has_fatal else [], "raw_instructions": instr_text}
                rows[row_num] = row_data
                row_order.append(row_num)
                source_order.append({"type": "row", "row_num": row_num})

            if row_num > max_claimed_row and row_num >= 1:
                max_claimed_row = row_num

        elif kw == "repeat":
            rep_match = re.match(r'^rows\s+(\d+)-(\d+)\s+x(.*)', after_kw)
            if not rep_match:
                errors.append(make_error("MALFORMED_REPEAT", f"Malformed repeat on line {line_num}.", line_num, None))
                i += 1
                continue
            r_start = int(rep_match.group(1))
            r_end = int(rep_match.group(2))
            count_raw = rep_match.group(3).strip()
            rep_errors_on_line = []

            count_valid = False
            count_val = 0
            if re.match(r'^\d+$', count_raw):
                count_val = int(count_raw)
                if count_val >= 1:
                    count_valid = True
            if not count_valid:
                rep_errors_on_line.append(make_error("INVALID_REPEAT_COUNT", f"Invalid repeat count on line {line_num}.", line_num, None))

            range_valid = True
            if r_start < 1 or r_end < 1 or r_start > r_end:
                range_valid = False
                rep_errors_on_line.append(make_error("INVALID_REPEAT_RANGE", f"Invalid repeat range on line {line_num}.", line_num, None))
            else:
                for rn in range(r_start, r_end + 1):
                    if rn not in rows:
                        range_valid = False
                        rep_errors_on_line.append(make_error("INVALID_REPEAT_RANGE", f"Repeat range references missing row {rn} on line {line_num}.", line_num, None))
                        break

            if has_valid_bind_off and has_valid_bind_off_line:
                errors.append(make_error("BIND_OFF_OUT_OF_ORDER", f"Repeat after bind_off on line {line_num}.", line_num, None))

            rep_entry = {
                "line": line_num,
                "start": r_start,
                "end": r_end,
                "count": count_val if count_valid else 0,
                "valid": count_valid and range_valid and not (has_valid_bind_off and has_valid_bind_off_line),
                "errors": rep_errors_on_line,
            }
            errors.extend(rep_errors_on_line)
            repeat_statements.append(rep_entry)
            source_order.append({"type": "repeat", "index": len(repeat_statements) - 1})

        elif kw == "bind_off":
            bo_match = re.match(r'^\s*$', after_kw)
            if bo_match:
                if has_valid_bind_off:
                    errors.append(make_error("DUPLICATE_BIND_OFF", f"Duplicate bind_off on line {line_num}.", line_num, None))
                has_valid_bind_off = True
                has_valid_bind_off_line = True
            else:
                errors.append(make_error("MALFORMED_BIND_OFF", f"Malformed bind_off on line {line_num}.", line_num, None))
                if has_valid_bind_off and has_valid_bind_off_line:
                    errors.append(make_error("BIND_OFF_OUT_OF_ORDER", f"Statement after bind_off on line {line_num}.", line_num, None))
                if not has_valid_bind_off:
                    pass

        i += 1

    if pattern_name is None and not any(e["code"] in ("MALFORMED_PATTERN", "DUPLICATE_PATTERN") for e in errors):
        errors.append(make_error("MISSING_PATTERN", "Missing pattern declaration.", None, None))

    if cast_on is None and not any(e["code"] in ("MALFORMED_CAST_ON", "DUPLICATE_CAST_ON") for e in errors):
        errors.append(make_error("MISSING_CAST_ON", "Missing cast_on declaration.", None, None))

    expanded_rows: list[dict] = []
    final_stitch_count: int | None = None

    source_sequence: list[int] = []
    for entry in source_order:
        if entry["type"] == "row":
            rn = entry["row_num"]
            if rn in rows and rows[rn]["state"] == "valid":
                source_sequence.append(rn)
        elif entry["type"] == "repeat":
            rep = repeat_statements[entry["index"]]
            if rep["valid"]:
                for _ in range(rep["count"]):
                    for rn in range(rep["start"], rep["end"] + 1):
                        if rn in rows and rows[rn]["state"] == "valid":
                            source_sequence.append(rn)

    if cast_on is not None and cast_on > 0:
            final_stitch_count = cast_on
            available_from_previous = cast_on
            sim_stopped = False
            for idx, rn in enumerate(source_sequence):
                rd = rows[rn]
                if sim_stopped:
                    break
                if rd["state"] != "valid":
                    continue
                if not rd["instructions"]:
                    err_inst = {"type": "error", "code": "STITCH_UNDERFLOW", "message": f"Row {rn} has no instructions.", "line": rd["line"], "row": rn}
                    if err_inst not in errors:
                        errors.append(err_inst)
                    sim_stopped = True
                    break
                start = available_from_previous
                remaining = available_from_previous
                row_produced = 0
                for inst in rd["instructions"]:
                    st = inst["stitch"]
                    ct = inst["count"]
                    consume, produce = STITCH_CONSUME_PRODUCE.get(st, (0, 0))
                    if st in ("k", "p"):
                        consume = ct
                        produce = ct
                    if consume > remaining:
                        err_under = {"type": "error", "code": "STITCH_UNDERFLOW", "message": f"Stitch underflow on row {rn}.", "line": rd["line"], "row": rn}
                        if err_under not in errors:
                            errors.append(err_under)
                        sim_stopped = True
                        break
                    remaining -= consume
                    row_produced += produce
                    if row_produced > 10000:
                        err_over = {"type": "error", "code": "STITCH_OVERFLOW", "message": f"Stitch overflow on row {rn}.", "line": rd["line"], "row": rn}
                        if err_over not in errors:
                            errors.append(err_over)
                        sim_stopped = True
                        break
                if sim_stopped:
                    break
                end = row_produced
                available_from_previous = end
                final_stitch_count = end
                expanded_row_obj = {
                    "expanded_row_index": idx + 1,
                    "source_row": rn,
                    "instructions": rd["instructions"],
                    "start_stitches": start,
                    "end_stitches": end,
                }
                expanded_rows.append(expanded_row_obj)

    valid = len(errors) == 0
    if errors:
        valid = False
        expanded_rows = []
        final_stitch_count = None

    sort_errors(errors)

    output = {
        "pattern_name": pattern_name,
        "cast_on": cast_on,
        "valid": valid,
        "errors": errors,
        "expanded_rows": expanded_rows,
        "final_stitch_count": final_stitch_count,
        "bind_off": has_valid_bind_off,
    }
    return json.dumps(output, indent=2)


def main():
    parser = argparse.ArgumentParser(description="Knitting Compiler")
    subparsers = parser.add_subparsers(dest="command")
    subparsers.required = True
    compile_parser = subparsers.add_parser("compile", help="Compile a .knit file")
    compile_parser.add_argument("input_file", help="Path to .knit file")

    args = parser.parse_args()

    if args.command == "compile":
        try:
            result = compile_file(args.input_file)
        except FileNotFoundError:
            print(f"Error: file not found: {args.input_file}", file=sys.stderr)
            sys.exit(2)
        except Exception as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(2)

        parsed = json.loads(result)
        if parsed["valid"]:
            print(result)
            sys.exit(0)
        else:
            print(result)
            sys.exit(1)


if __name__ == "__main__":
    main()
