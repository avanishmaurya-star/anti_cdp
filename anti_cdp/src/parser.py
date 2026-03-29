import re

def parse_gcc_errors(raw_output):
    """
    Parses raw GCC error output into a list of structured error objects.
    
    Args:
        raw_output (str): The stderr output from GCC.
        
    Returns:
        list: A list of dicts, where each dict represents an error/warning.
    """
    errors = []
    # Regex to capture: file:line:col: type: message
    # Example: data/sample_error.cpp:5:5: error: 'y' was not declared in this scope
    error_pattern = re.compile(r"^(.+):(\d+):(\d+):\s+(error|warning|fatal error):\s+(.+)$")
    
    # Regex for linker errors (undefined reference)
    # Example: C:\Users\...\ccQ3oSg5.o:linker_error.cpp:(.text+0xc): undefined reference to `missingFunction()'
    linker_pattern = re.compile(r"^.+:(.+):\(.+\):\s+undefined reference to\s+`(.+)'$")

    lines = raw_output.split('\n')
    for line in lines:
        match = error_pattern.match(line.strip())
        if match:
            errors.append({
                'file': match.group(1),
                'line': int(match.group(2)),
                'column': int(match.group(3)),
                'type': match.group(4),
                'message': match.group(5).strip()
            })
            continue
            
        linker_match = linker_pattern.match(line.strip())
        if linker_match:
             errors.append({
                'file': linker_match.group(1),
                'line': 0, # Linker errors often don't have exact line numbers easily accessible here
                'column': 0,
                'type': 'linker error',
                'message': f"undefined reference to {linker_match.group(2)}"
            })
            
    return errors
