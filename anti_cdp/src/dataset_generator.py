import os
import sys
import json
import glob

# Ensure the 'src' directory is in the Python path for local imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from capture import capture_gcc_output
from parser import parse_gcc_errors
from explainer import explain_error
from ast_extractor import generate_ast
from ast_context import enrich_errors_with_ast

def generate_dataset(data_dir: str, output_file: str):
    """
    Generates a raw dataset from C++ files in the given directory.
    """
    cpp_files = glob.glob(os.path.join(data_dir, "*.cpp"))
    
    if not cpp_files:
        print(f"No .cpp files found in {data_dir}")
        return

    dataset = []

    for cpp_file in cpp_files:
        print(f"Processing: {cpp_file}")
        
        raw_output = capture_gcc_output(cpp_file)
        if not raw_output:
            print(f"  Skipping {cpp_file}: Compilation Successful")
            continue
            
        errors = parse_gcc_errors(raw_output)
        if not errors:
            print(f"  Skipping {cpp_file}: Could not parse GCC errors")
            continue
            
        ast_result = generate_ast(cpp_file)
        enriched_errors = enrich_errors_with_ast(errors, ast_result)
        
        for err in enriched_errors:
            explanation = explain_error(err)
            
            # Read the full source code for context
            try:
                with open(cpp_file, 'r', encoding='utf-8') as f:
                    source_code = f.read()
            except Exception as e:
                source_code = f"Error reading file: {e}"
            
            entry = {
                "file": cpp_file,
                "original_source": source_code,
                "error_type": err.get("type", "error"),
                "error_message": err.get("message", ""),
                "line": err.get("line", 0),
                "column": err.get("column", 0),
                "ast_context": err.get("ast_context", {}),
                "annotation": explanation
            }
            dataset.append(entry)
            
    try:
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(dataset, f, indent=4)
        print(f"\nSuccessfully generated dataset with {len(dataset)} entries at {output_file}")
    except Exception as e:
        print(f"\nFailed to save dataset: {e}")

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python src/dataset_generator.py <data_directory> <output_json_path>")
        sys.exit(1)
        
    data_directory = sys.argv[1]
    output_path = sys.argv[2]
    
    # Ensure src directory is in path so imports work when running from project root
    sys.path.append(os.path.dirname(os.path.abspath(__file__)))
    
    generate_dataset(data_directory, output_path)
