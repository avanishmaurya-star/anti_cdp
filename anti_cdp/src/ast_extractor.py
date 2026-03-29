"""
ast_extractor.py – Week 7: AST Context Extraction Module
=========================================================
Responsibilities:
  1. Generate a Clang AST dump for a given C++ source file.
  2. Parse the raw Clang AST dump into a list of structured node dicts.
  3. Map compiler errors (file + line + column) to the closest AST nodes.
  4. Extract a "context window" of AST nodes surrounding each error.

Clang is used because it produces rich, machine-readable AST dumps via:
    clang++ -Xclang -ast-dump -fsyntax-only <file>

If Clang is not installed the module falls back gracefully and returns
a minimal synthetic AST node built purely from the source-file text.
"""

import subprocess
import re
import os
from typing import Optional


# ---------------------------------------------------------------------------
# 1. AST GENERATION
# ---------------------------------------------------------------------------

def generate_ast(file_path: str) -> dict:
    """
    Run Clang's AST dump on *file_path* and return a result dict:

        {
            "success":   bool,
            "raw_dump":  str,          # full stdout of clang -ast-dump
            "error":     str | None,   # human-readable problem if success=False
            "source":    list[str],    # source lines (1-indexed via source[line-1])
        }
    """
    result = {
        "success": False,
        "raw_dump": "",
        "error": None,
        "source": [],
    }

    if not os.path.exists(file_path):
        result["error"] = f"File not found: {file_path}"
        return result

    # Store source lines for context extraction even if Clang fails
    try:
        with open(file_path, "r", encoding="utf-8", errors="replace") as fh:
            result["source"] = fh.readlines()
    except OSError as exc:
        result["error"] = f"Cannot read source file: {exc}"
        return result

    # Attempt Clang AST dump
    try:
        proc = subprocess.run(
            [
                "clang++",
                "-Xclang", "-ast-dump",
                "-fsyntax-only",
                "-fno-color-diagnostics",      # no ANSI codes
                file_path,
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=30,
        )
        # clang -ast-dump writes AST to stdout; errors/warnings go to stderr.
        # A non-zero returncode just means there were compile errors – that is
        # expected, we still get the partial AST on stdout.
        raw = proc.stdout.strip()
        if raw:
            result["success"] = True
            result["raw_dump"] = raw
        else:
            result["error"] = "Clang produced no AST output (is clang++ installed?)"
    except FileNotFoundError:
        result["error"] = (
            "clang++ not found. Install LLVM/Clang and make sure it is in PATH. "
            "Falling back to source-line context only."
        )
    except subprocess.TimeoutExpired:
        result["error"] = "Clang AST dump timed out after 30 s."

    return result


# ---------------------------------------------------------------------------
# 2. AST DUMP PARSING
# ---------------------------------------------------------------------------

# Matches lines like:
#   `-VarDecl 0x... <line:4:5, col:13> col:9 x 'int' cinit
#   |-FunctionDecl 0x... <line:3:1, col:12> line:3:5 main 'int ()'
#   | `-CompoundStmt 0x... <col:13, line:8:1>
_NODE_RE = re.compile(
    r"^(?P<indent>[| `\-\\/ ]*)?"               # tree indentation prefix
    r"(?P<kind>[A-Z][A-Za-z]+)"                 # node kind, e.g. VarDecl
    r".*?"                                       # misc tokens
    r"<(?:(?:line|col):(?P<start_line>\d+)"     # optional <line:N or <col:N
    r"(?::(?P<start_col>\d+))?,?\s*"
    r"(?:(?:line|col):(?P<end_line>\d+)"
    r"(?::(?P<end_col>\d+))?)?)>"               # closing >
    r"(?:.*?(?:line:(?P<def_line>\d+)"          # definition line (col:N line:N …)
    r"(?::(?P<def_col>\d+))?))?"
    r"(?P<rest>.*?)$"
)


def parse_ast_dump(raw_dump: str) -> list[dict]:
    """
    Parse the raw Clang AST dump text into a list of node dicts.

    Each node dict contains:
        kind       (str)  – e.g. "FunctionDecl", "VarDecl", "BinaryOperator"
        line       (int)  – best-guess source line (0 = unknown)
        col        (int)  – best-guess source column (0 = unknown)
        end_line   (int)  – end of node range
        end_col    (int)  – end of node range
        depth      (int)  – tree depth (indentation level)
        raw        (str)  – the original dump line
    """
    nodes = []
    for raw_line in raw_dump.splitlines():
        if not raw_line.strip():
            continue
        m = _NODE_RE.match(raw_line)
        if not m:
            continue

        indent_str = m.group("indent") or ""
        # Depth ≈ number of tree-drawing chars / 2
        depth = len(indent_str) // 2

        def _int(val: Optional[str]) -> int:
            return int(val) if val else 0

        # Prefer the "def_line" field (the actual definition location) over the
        # range start, because they convey different things:
        #   range start = beginning of the whole sub-tree
        #   def_line    = where this specific node is written
        line = _int(m.group("def_line")) or _int(m.group("start_line"))
        col  = _int(m.group("def_col"))  or _int(m.group("start_col"))

        nodes.append({
            "kind":     m.group("kind"),
            "line":     line,
            "col":      col,
            "end_line": _int(m.group("end_line")),
            "end_col":  _int(m.group("end_col")),
            "depth":    depth,
            "raw":      raw_line.rstrip(),
        })

    return nodes


# ---------------------------------------------------------------------------
# 3. MAP ERROR → AST NODES
# ---------------------------------------------------------------------------

def find_ast_nodes_at_line(nodes: list[dict], target_line: int,
                            target_col: int = 0,
                            window: int = 2) -> list[dict]:
    """
    Return all AST nodes whose line is within *window* lines of *target_line*.
    Nodes are returned in document order (depth-first, as they appear in the dump).

    Args:
        nodes       – output of parse_ast_dump()
        target_line – the error's line number (1-based)
        target_col  – the error's column number (0 = ignore)
        window      – how many lines before/after to include
    """
    if not nodes:
        return []

    lo = max(1, target_line - window)
    hi = target_line + window

    matched = []
    for node in nodes:
        if node["line"] == 0:
            continue
        if lo <= node["line"] <= hi:
            matched.append(node)

    return matched


# ---------------------------------------------------------------------------
# 4. EXTRACT SURROUNDING AST CONTEXT
# ---------------------------------------------------------------------------

def extract_ast_context(
    nodes: list[dict],
    source_lines: list[str],
    error_line: int,
    error_col: int = 0,
    node_window: int = 3,
    source_window: int = 3,
) -> dict:
    """
    Build a rich context dict for a single error location.

    Returns:
        {
            "error_line":       int,
            "error_col":        int,
            "source_snippet":   list[dict],  # {"lineno", "text", "is_error"}
            "ast_nodes":        list[dict],  # nearby AST nodes
            "enclosing_func":   str | None,  # nearest enclosing FunctionDecl name
            "enclosing_class":  str | None,  # nearest enclosing CXXRecordDecl name
            "node_kinds":       list[str],   # unique AST kinds in window
        }
    """
    context: dict = {
        "error_line": error_line,
        "error_col":  error_col,
        "source_snippet": [],
        "ast_nodes": [],
        "enclosing_func": None,
        "enclosing_class": None,
        "node_kinds": [],
    }

    # ── Source snippet ──────────────────────────────────────────────────────
    lo = max(1, error_line - source_window)
    hi = min(len(source_lines), error_line + source_window)
    for ln in range(lo, hi + 1):
        text = source_lines[ln - 1].rstrip() if ln <= len(source_lines) else ""
        context["source_snippet"].append({
            "lineno":   ln,
            "text":     text,
            "is_error": ln == error_line,
        })

    if not nodes:
        return context

    # ── Nearby AST nodes ────────────────────────────────────────────────────
    nearby = find_ast_nodes_at_line(nodes, error_line, error_col, window=node_window)
    context["ast_nodes"] = nearby
    context["node_kinds"] = list({n["kind"] for n in nearby})

    # ── Enclosing function / class ──────────────────────────────────────────
    # Walk backwards through all nodes that appear *before or at* the error line
    # and pick the most recent FunctionDecl / CXXRecordDecl still "open" (i.e.
    # whose end_line >= error_line, or end_line == 0 meaning unknown).
    preceding = [n for n in nodes if 0 < n["line"] <= error_line]

    for node in reversed(preceding):
        if node["kind"] in ("FunctionDecl", "CXXMethodDecl", "LambdaExpr"):
            if context["enclosing_func"] is None:
                # Extract the function name from the raw dump line
                context["enclosing_func"] = _extract_name(node["raw"])
        if node["kind"] in ("CXXRecordDecl", "ClassTemplateDecl"):
            if context["enclosing_class"] is None:
                context["enclosing_class"] = _extract_name(node["raw"])
        if context["enclosing_func"] and context["enclosing_class"]:
            break

    return context


# ---------------------------------------------------------------------------
# HELPERS
# ---------------------------------------------------------------------------

_NAME_RE = re.compile(
    r"(?:referenced\s+)?(?:used\s+)?"
    r"(?:implicit\s+)?(?:constexpr\s+)?"
    r"([A-Za-z_][A-Za-z0-9_:~]*)"   # identifier
    r"\s+'[^']+'"                    # followed by quoted type
)

def _extract_name(raw_line: str) -> Optional[str]:
    """Best-effort extraction of an identifier name from a raw AST dump line."""
    # Remove the leading tree-drawing characters and the node kind
    # e.g.: "|-FunctionDecl 0x... <...> line:3:5 main 'int ()'"
    # After the angle-bracket range, we typically have: "line:N:C <name> '<type>'"
    # We look for the pattern: word followed by quoted type
    after_range = re.sub(r"<[^>]*>", "", raw_line)   # strip <...> spans
    after_range = re.sub(r"0x[0-9a-fA-F]+", "", after_range)  # strip hex addrs
    m = _NAME_RE.search(after_range)
    if m:
        return m.group(1)
    return None
