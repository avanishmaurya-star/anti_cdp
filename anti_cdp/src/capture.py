import subprocess
import os

def capture_gcc_output(file_path):
    """
    Compiles the given C++ file using g++ and captures the stderr output.
    
    Args:
        file_path (str): Path to the C++ source file.
        
    Returns:
        str: The raw error output from GCC.
    """
    if not os.path.exists(file_path):
        return f"Error: File '{file_path}' not found."

    try:
        # We use -fno-diagnostics-show-caret to get cleaner error messages for parsing initially,
        # but for now let's stick to default to see what we get.
        # Actually, let's keep it simple.
        result = subprocess.run(
            ['g++', file_path, '-o', 'temp_executable'],
            stderr=subprocess.PIPE,
            stdout=subprocess.PIPE,
            text=True
        )
        # Clean up the executable if it was created (unlikely with errors)
        if os.path.exists('temp_executable'):
            os.remove('temp_executable')
        elif os.path.exists('temp_executable.exe'):
            os.remove('temp_executable.exe')
            
        return result.stderr
    except FileNotFoundError:
        return "Error: 'g++' compiler not found. Please ensure GCC is installed and in your PATH."
