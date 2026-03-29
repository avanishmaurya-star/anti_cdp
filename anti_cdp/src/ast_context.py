"""
ast_context.py – Week 7: Context-Enriched Error Representations
================================================================
Takes the structured errors produced by parser.py and enriches each one
with AST context from ast_extractor.py.

Public API
----------
enrich_errors_with_ast(errors, ast_result)  →  list[dict]
format_enriched_error(enriched_error)       →  str
"""

from ast_extractor import (
    parse_ast_dump,
    extract_ast_context,
)


# ---------------------------------------------------------------------------
# 1. ENRICH ERRORS WITH AST CONTEXT
# ---------------------------------------------------------------------------

def enrich_errors_with_ast(errors: list[dict], ast_result: dict) -> list[dict]:
    """
    Merge each structured error with AST context information.

    Args:
        errors     – list of error dicts from parser.parse_gcc_errors()
        ast_result – dict returned by ast_extractor.generate_ast()

    Returns:
        A new list of enriched error dicts. Each dict extends the original
        error dict with an extra key ``"ast_context"`` containing the dict
        returned by extract_ast_context().
    """
    # Parse the AST dump once (empty list if Clang wasn't available)
    nodes = parse_ast_dump(ast_result.get("raw_dump", "")) if ast_result.get("success") else []
    source_lines = ast_result.get("source", [])

    enriched = []
    for error in errors:
        line = error.get("line", 0)
        col  = error.get("column", 0)

        context = extract_ast_context(
            nodes=nodes,
            source_lines=source_lines,
            error_line=line,
            error_col=col,
        )

        enriched_error = dict(error)  # shallow copy of original error fields
        enriched_error["ast_context"] = context
        enriched.append(enriched_error)

    return enriched


# ---------------------------------------------------------------------------
# 2. FORMAT ENRICHED ERROR
# ---------------------------------------------------------------------------

_KIND_LABELS = {
    "FunctionDecl":        "Function Declaration",
    "CXXMethodDecl":       "Method Declaration",
    "VarDecl":             "Variable Declaration",
    "ParmVarDecl":         "Parameter Declaration",
    "CallExpr":            "Function Call",
    "DeclRefExpr":         "Variable Reference",
    "BinaryOperator":      "Binary Operation",
    "UnaryOperator":       "Unary Operation",
    "ReturnStmt":          "Return Statement",
    "IfStmt":              "If Statement",
    "CompoundStmt":        "Code Block",
    "DeclStmt":            "Declaration Statement",
    "CXXRecordDecl":       "Class Declaration",
    "CXXConstructorDecl":  "Constructor",
    "CXXDestructorDecl":   "Destructor",
    "MemberExpr":          "Member Access",
    "ArraySubscriptExpr":  "Array Access",
    "ImplicitCastExpr":    "Implicit Type Cast",
    "TypedefDecl":         "Typedef Declaration",
    "NamespaceDecl":       "Namespace",
}


def format_enriched_error(enriched: dict) -> str:
    """
    Produce a rich, human-readable string for one enriched error dict.

    The output is structured in three sections:
        [Location]   – file, line, column, error type
        [AST Context]– surrounding AST nodes with semantic labels
        [Source]     – annotated source snippet
    """
    lines = []

    # ── Header ──────────────────────────────────────────────────────────────
    etype   = enriched.get("type", "error").upper()
    efile   = enriched.get("file", "?")
    eline   = enriched.get("line", 0)
    ecol    = enriched.get("column", 0)
    emsg    = enriched.get("message", "")

    lines.append(f"{'='*60}")
    lines.append(f"  {etype}  at {efile}:{eline}:{ecol}")
    lines.append(f"  {emsg}")
    lines.append(f"{'='*60}")

    ctx = enriched.get("ast_context", {})

    # ── Enclosing scope ──────────────────────────────────────────────────────
    func  = ctx.get("enclosing_func")
    klass = ctx.get("enclosing_class")
    if klass:
        lines.append(f"  Enclosing Class   : {klass}")
    if func:
        lines.append(f"  Enclosing Function: {func}")
    if func or klass:
        lines.append("")

    # ── Source snippet ───────────────────────────────────────────────────────
    snippet = ctx.get("source_snippet", [])
    if snippet:
        lines.append("  Source:")
        for item in snippet:
            marker = ">" if item["is_error"] else " "
            lines.append(f"  {marker} {item['lineno']:4d} | {item['text']}")
        # Column pointer
        if ecol > 0 and snippet:
            arrow_pad = " " * (ecol + 9)   # 9 = "  > NNNN | "
            lines.append(f"{arrow_pad}^")
        lines.append("")

    # ── AST nodes ────────────────────────────────────────────────────────────
    ast_nodes = ctx.get("ast_nodes", [])
    if ast_nodes:
        lines.append("  Nearby AST Nodes:")
        for node in ast_nodes:
            label = _KIND_LABELS.get(node["kind"], node["kind"])
            loc   = f"line {node['line']}" + (f", col {node['col']}" if node.get("col") else "")
            indent = "  " + "  " * min(node.get("depth", 0), 4)
            lines.append(f"{indent}• [{label}] at {loc}")
        lines.append("")
    else:
        lines.append("  AST Nodes: (not available - Clang not installed or parse failed)")
        lines.append("")

    # ── Semantic hint ────────────────────────────────────────────────────────
    node_kinds = ctx.get("node_kinds", [])
    hint = _semantic_hint(emsg, node_kinds)
    if hint:
        lines.append(f"  AST Hint: {hint}")
        lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# HELPERS
# ---------------------------------------------------------------------------

def _semantic_hint(message: str, node_kinds: list[str]) -> str:
    """Generate a short semantic hint by correlating the error message with
    the surrounding AST node kinds."""

    if "was not declared in this scope" in message:
        if "DeclRefExpr" in node_kinds:
            return ("A DeclRefExpr (variable reference) is present near this error. "
                    "The identifier exists in the AST but cannot be resolved - "
                    "likely used before declaration or out of scope.")
        return "No declaration node found near this line - the symbol is completely undefined."

    if "expected" in message and ("';'" in message or "')'" in message):
        if "CompoundStmt" in node_kinds or "BinaryOperator" in node_kinds:
            return ("A statement or expression is present in the AST. "
                    "A missing ';' or ')' breaks parsing before the next token.")

    if "undefined reference" in message:
        if "CallExpr" in node_kinds:
            return ("A CallExpr is present – you are calling a function that has "
                    "no corresponding definition visible to the linker.")
        return "No function call AST node visible – check whether the function is declared."

    if "cannot convert" in message or "conversion from" in message:
        if "ImplicitCastExpr" in node_kinds:
            return ("An ImplicitCastExpr is present. The compiler attempted an automatic "
                    "conversion but it is not allowed between these types.")
        if "BinaryOperator" in node_kinds or "DeclStmt" in node_kinds:
            return "An assignment or binary operation involves incompatible types."

    if "too few arguments" in message or "too many arguments" in message or \
       "no matching function" in message:
        if "CallExpr" in node_kinds:
            return ("A CallExpr node is present. The argument count or types in the "
                    "call do not match any visible overload.")

    if "is private" in message:
        if "MemberExpr" in node_kinds:
            return ("A MemberExpr is present - you are accessing a class member "
                    "that is declared private.")

    if "assignment of read-only" in message:
        if "BinaryOperator" in node_kinds:
            return ("A BinaryOperator (assignment) targets a const-qualified variable. "
                    "Remove 'const' or remove the assignment.")

    return ""
