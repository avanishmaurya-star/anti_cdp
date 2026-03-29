import sys
import json
import os

def clean_dataset(input_file: str, output_file: str):
    """
    Cleans and normalizes the raw dataset.
    """
    try:
        with open(input_file, 'r', encoding='utf-8') as f:
            dataset = json.load(f)
    except Exception as e:
        print(f"Error reading input file: {e}")
        return

    cleaned_dataset = []
    seen_hashes = set()

    for entry in dataset:
        # Strip absolute paths from the file name, keep only the basename
        if "file" in entry:
            entry["file"] = os.path.basename(entry["file"])
            
        # Clean paths within the exact matching source snippets if any
        if "ast_context" in entry and "source_snippet" in entry["ast_context"]:
             for snippet in entry["ast_context"]["source_snippet"]:
                 # Just standardizing spacing, not strictly necessary but good practice
                 snippet["text"] = snippet["text"].replace('\t', '    ')

        # Create a unique hash for the entry to avoid perfect duplicates
        # Duplicates can happen if a single file triggers the exact same error multiple times inappropriately
        entry_hash = hash(f"{entry['file']}|{entry['line']}|{entry['column']}|{entry['error_message']}")
        
        if entry_hash not in seen_hashes:
            seen_hashes.add(entry_hash)
            cleaned_dataset.append(entry)

    try:
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(cleaned_dataset, f, indent=4)
        print(f"Successfully cleaned dataset. Reduced from {len(dataset)} to {len(cleaned_dataset)} entries.")
        print(f"Saved to {output_file}")
    except Exception as e:
        print(f"Failed to save cleaned dataset: {e}")
        
if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python src/dataset_cleaner.py <input_json_path> <output_json_path>")
        sys.exit(1)
        
    input_path = sys.argv[1]
    output_path = sys.argv[2]
    
    clean_dataset(input_path, output_path)
