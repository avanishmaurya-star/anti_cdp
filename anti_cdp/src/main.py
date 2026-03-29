import sys
import os

# Ensure the 'src' directory is in the Python path for local imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from capture import capture_gcc_output
from parser import parse_gcc_errors
from explainer import explain_error
from ast_extractor import generate_ast
from ast_context import enrich_errors_with_ast, format_enriched_error


def main():
    if len(sys.argv) < 2:
        print("Usage: python src/main.py <path_to_cpp_file>")
        return

    cpp_file = sys.argv[1]

    print(f"--- Processing {cpp_file} ---\n")

    # ── Step 1: Capture GCC output ──────────────────────────────────────────
    raw_output = capture_gcc_output(cpp_file)
    if not raw_output:
        print("[OK] Compilation Successful! No errors found.")
        return

    # ── Step 2: Parse GCC errors ────────────────────────────────────────────
    errors = parse_gcc_errors(raw_output)

    if not errors:
        print("[WARN]  Compilation failed, but no structured errors were parsed.")
        print("Raw GCC Output:")
        print(raw_output)
        return

    # ── Step 3: Generate AST (Clang) ────────────────────────────────────────
    print("Generating AST with Clang...")
    ast_result = generate_ast(cpp_file)

    if ast_result["success"]:
        print(f"   [OK] AST generated ({len(ast_result['raw_dump'].splitlines())} nodes)\n")
    else:
        print(f"   [WARN] AST unavailable: {ast_result['error']}")
        print("   (Source-line context will still be shown)\n")

    # ── Step 4: Enrich errors with AST context ──────────────────────────────
    enriched_errors = enrich_errors_with_ast(errors, ast_result)

    # ── Step 5: Explain + format ────────────────────────────────────────────
    print(f"Found {len(enriched_errors)} issue(s):\n")

    for i, err in enumerate(enriched_errors, 1):
        explanation = explain_error(err)

        # Rich AST-context report
        print(format_enriched_error(err))

        # NLP explanation from Week 6
        print(f"  [Explanation]:")
        for line in explanation.splitlines():
            print(f"     {line}")
        print()


if __name__ == "__main__":
    main()
