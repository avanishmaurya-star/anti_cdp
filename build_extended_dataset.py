"""
Builds an extended dataset (extended_dataset.json) with richer synthetic entries
that match the clean_dataset.json schema exactly.
"""
import json, os

BASE = os.path.dirname(os.path.abspath(__file__))

def make_entry(file, source, error_type, error_message, line, col, snippet_lines, error_line_idx, annotation):
    snippet = []
    for i, text in enumerate(snippet_lines):
        snippet.append({"lineno": line - error_line_idx + i, "text": text, "is_error": i == error_line_idx})
    return {
        "file": file,
        "original_source": source,
        "error_type": error_type,
        "error_message": error_message,
        "line": line,
        "column": col,
        "ast_context": {
            "error_line": line,
            "error_col": col,
            "source_snippet": snippet,
            "ast_nodes": [], "enclosing_func": None, "enclosing_class": None, "node_kinds": []
        },
        "annotation": annotation
    }

ENTRIES = [
  # ── Variable Declaration ─────────────────────────────────────────────────
  make_entry("undeclared1.cpp","int main(){return z;}","error",
    "'z' was not declared in this scope",1,14,
    ["int main(){","    return z;","}"],1,
    "Programming Concept: Variable Declaration.\nExplanation: You are trying to use the variable 'z', but the compiler does not know it exists at this point.\nFix: Declare the variable before using it: 'int z = 0;'"),

  make_entry("undeclared2.cpp","void f(){count++;}","error",
    "'count' was not declared in this scope",1,9,
    ["void f(){","    count++;","}"],1,
    "Programming Concept: Variable Declaration.\nExplanation: 'count' is used but never declared in this scope.\nFix: Add 'int count = 0;' before the function or as a parameter."),

  make_entry("undeclared3.cpp","int main(){if(flag){}}","error",
    "'flag' was not declared in this scope",1,11,
    ["int main(){","    if(flag){}","}"],1,
    "Programming Concept: Variable Declaration.\nExplanation: 'flag' is referenced without being declared.\nFix: Declare 'bool flag = false;' before use."),

  # ── Syntax Rules ─────────────────────────────────────────────────────────
  make_entry("syntax1.cpp","int main(){int x=5\nreturn 0;}","error",
    "expected ';' before 'return'",2,1,
    ["int main(){","    int x=5","    return 0;","}"],1,
    "Programming Concept: Syntax Rules.\nExplanation: Every statement in C++ must end with a semicolon. The compiler reached 'return' before seeing the ';'.\nFix: Add ';' at the end of 'int x=5'."),

  make_entry("syntax2.cpp","int main(){\nint arr[5]\nreturn 0;\n}","error",
    "expected ';' before 'return'",3,1,
    ["int main(){","    int arr[5]","    return 0;","}"],1,
    "Programming Concept: Syntax Rules.\nExplanation: Missing semicolon after array declaration.\nFix: Write 'int arr[5];'"),

  make_entry("syntax3.cpp","int main(){\nif(x > 0\n    x++;\n}","error",
    "expected ')' before 'x'",3,4,
    ["int main(){","    if(x > 0","        x++;","}"],1,
    "Programming Concept: Syntax Rules.\nExplanation: The closing parenthesis of the 'if' condition is missing.\nFix: Write 'if(x > 0)'"),

  make_entry("syntax4.cpp","int main(){\nfor(int i=0 i<10; i++){}\n}","error",
    "expected ';' before 'i'",2,12,
    ["int main(){","    for(int i=0 i<10; i++){}","}"],1,
    "Programming Concept: Syntax Rules.\nExplanation: The 'for' loop requires semicolons between its three parts.\nFix: Write 'for(int i=0; i<10; i++)'"),

  # ── Linking ──────────────────────────────────────────────────────────────
  make_entry("link1.cpp","int add(int,int);\nint main(){return add(1,2);}","error",
    "undefined reference to 'add(int, int)'",2,15,
    ["int add(int,int);","int main(){","    return add(1,2);","}"],2,
    "Programming Concept: Linking.\nExplanation: 'add' is declared but never defined. The linker cannot find the function body.\nFix: Provide the definition: 'int add(int a,int b){return a+b;}'"),

  make_entry("link2.cpp","extern int globalVal;\nint main(){return globalVal;}","error",
    "undefined reference to 'globalVal'",2,15,
    ["extern int globalVal;","int main(){","    return globalVal;","}"],2,
    "Programming Concept: Linking.\nExplanation: 'globalVal' is declared with 'extern' but not defined in any translation unit.\nFix: Define it in exactly one .cpp file: 'int globalVal = 0;'"),

  # ── Encapsulation ─────────────────────────────────────────────────────────
  make_entry("access1.cpp","class A{private: int v;};\nint main(){A a; a.v=1;}","error",
    "'int A::v' is private within this context",2,18,
    ["class A{private: int v;};","int main(){","    A a;","    a.v=1;","}"],3,
    "Programming Concept: Encapsulation (Access Modifiers).\nExplanation: 'v' is private and cannot be accessed outside class A.\nFix: Add a public setter: 'void setV(int x){ v=x; }'"),

  make_entry("access2.cpp","class B{protected: double d;};\nclass C:public B{};\nint main(){C c; c.d=3.14;}","error",
    "'double B::d' is protected within this context",3,15,
    ["class B{protected: double d;};","class C:public B{};","int main(){C c;","    c.d=3.14;","}"],3,
    "Programming Concept: Encapsulation (Access Modifiers).\nExplanation: 'protected' members are accessible within derived classes but not from outside.\nFix: Access 'd' through a method inside C, or change its visibility to public."),

  # ── Constants ─────────────────────────────────────────────────────────────
  make_entry("const1.cpp","int main(){const int N=10; N=20;}","error",
    "assignment of read-only variable 'N'",1,26,
    ["int main(){","    const int N=10;","    N=20;","}"],2,
    "Programming Concept: Constants.\nExplanation: 'const' variables cannot be modified after initialisation.\nFix: Remove 'const' if the value must change, or use a different variable."),

  make_entry("const2.cpp","void f(const int& x){x++;}","error",
    "increment of read-only reference 'x'",1,22,
    ["void f(const int& x){","    x++;","}"],1,
    "Programming Concept: Constants.\nExplanation: 'x' is a const reference — it guarantees the original value is not modified.\nFix: Remove 'const' from the parameter if you need to modify it."),

  make_entry("const3.cpp","const double PI=3.14;\nint main(){PI=3.0;}","error",
    "assignment of read-only variable 'PI'",2,11,
    ["const double PI=3.14;","int main(){","    PI=3.0;","}"],2,
    "Programming Concept: Constants.\nExplanation: PI is a compile-time constant and cannot be reassigned.\nFix: Use a different variable for the modified value."),

  # ── Function Signatures ───────────────────────────────────────────────────
  make_entry("sig1.cpp","void print(int x,int y);\nint main(){print(5);}","error",
    "too few arguments to function 'void print(int, int)'",2,11,
    ["void print(int x,int y);","int main(){","    print(5);","}"],2,
    "Programming Concept: Function Signatures.\nExplanation: 'print' expects 2 arguments but only 1 was given.\nFix: Call as 'print(5, 0)' or add a default parameter."),

  make_entry("sig2.cpp","int square(int x);\nint main(){square(2,3);}","error",
    "too many arguments to function 'int square(int)'",2,11,
    ["int square(int x);","int main(){","    square(2,3);","}"],2,
    "Programming Concept: Function Signatures.\nExplanation: 'square' takes 1 argument, but 2 were provided.\nFix: Call as 'square(2)' or update the function signature."),

  make_entry("sig3.cpp","void greet(std::string name);\nint main(){greet(42);}","error",
    "invalid conversion from 'int' to 'std::string'",2,11,
    ["void greet(std::string name);","int main(){","    greet(42);","}"],2,
    "Programming Concept: Function Signatures.\nExplanation: You passed an int where a string is expected — types do not match.\nFix: Pass a string literal: 'greet(\"Alice\")'"),

  make_entry("sig4.cpp","template<class T>\nvoid show(T val);\nint main(){show();}","error",
    "no matching function for call to 'show()'",3,11,
    ["template<class T>","void show(T val);","int main(){","    show();","}"],3,
    "Programming Concept: Function Signatures.\nExplanation: Template function 'show' cannot be instantiated without an argument.\nFix: Provide an argument: 'show(42)' or 'show(\"hello\")'"),

  # ── General Error (missing headers / misc) ────────────────────────────────
  make_entry("hdr1.cpp","int main(){std::set<int> s;}","error",
    "'set' is not a member of 'std'",1,15,
    ["int main(){","    std::set<int> s;","}"],1,
    "Programming Concept: General Error.\nExplanation: 'std::set' requires the <set> header.\nFix: Add '#include <set>' at the top of your file."),

  make_entry("hdr2.cpp","int main(){std::queue<int> q;}","error",
    "'queue' is not a member of 'std'",1,15,
    ["int main(){","    std::queue<int> q;","}"],1,
    "Programming Concept: General Error.\nExplanation: std::queue requires the <queue> header.\nFix: Add '#include <queue>' at the top."),

  make_entry("hdr3.cpp","int main(){printf(\"%d\",1);}","error",
    "'printf' was not declared in this scope",1,11,
    ["int main(){","    printf(\"%d\",1);","}"],1,
    "Programming Concept: General Error.\nExplanation: 'printf' is a C function that requires <cstdio>.\nFix: Add '#include <cstdio>' or use 'std::cout' with <iostream>."),

  make_entry("hdr4.cpp","int main(){std::stack<int> s;}","error",
    "'stack' is not a member of 'std'",1,15,
    ["int main(){","    std::stack<int> s;","}"],1,
    "Programming Concept: General Error.\nExplanation: std::stack requires the <stack> header.\nFix: Add '#include <stack>' at the top."),
]

out_path = os.path.join(BASE, "anti_cdp", "data", "extended_dataset.json")
with open(out_path, "w") as f:
    json.dump(ENTRIES, f, indent=2)
print(f"Written {len(ENTRIES)} extended entries → {out_path}")
