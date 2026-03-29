def explain_error(error_info):
    """
    Generates a human-readable explanation for a given error object.
    
    Args:
        error_info (dict): The structured error info containing message, line, etc.
        
    Returns:
        str: A user-friendly explanation.
    """
    message = error_info['message']
    
    # Rule-based explanations
    if "was not declared in this scope" in message:
        variable = message.split("'")[1] if "'" in message else "a variable"
        return (
            f"Programming Concept: Variable Declaration.\n"
            f"Explanation: You are trying to use the variable '{variable}', but the compiler doesn't know what it is.\n"
            f"Fix: Make sure you have declared '{variable}' contents (e.g., 'int {variable};') before using it. "
            f"Also check for typos."
        )
        
    if "expected" in message and ("before" in message or "after" in message):
        # Example: expected ';' before 'return'
        return (
            f"Programming Concept: Syntax Rules.\n"
            f"Explanation: The compiler is confused because it expected something else here.\n"
            f"Technical Trace: {message}\n"
            f"Fix: Look at the line *before* line {error_info['line']}. You might be missing a semicolon ';' or a closing parenthesis ')'."
        )
        
    if "undefined reference to" in message:
        return (
            f"Programming Concept: Linking.\n"
            f"Explanation: You declared a function but didn't define it, or you forgot to link a library.\n"
            f"Fix: Check if you have implemented all your functions."
        )

    # 1. Type Mismatch
    if ("conversion from" in message and "requested" in message) or "invalid user-defined conversion" in message or "cannot convert" in message:
        return (
            f"Programming Concept: Data Types.\n"
            f"Explanation: You are trying to assign a value of one type to a variable of a different, incompatible type.\n"
            f"Fix: Check the variable types on line {error_info['line']}. Ensure they match or are compatible (e.g., don't assign a string to an int)."
        )

    # 2. Missing Header
    if "incomplete type" in message or "was not declared in this scope" in message and ("cout" in message or "cin" in message or "vector" in message or "string" in message):
        valid_headers = {
            "cout": "<iostream>",
            "cin": "<iostream>",
            "vector": "<vector>",
            "string": "<string>"
        }
        missing = "the appropriate header"
        for key, val in valid_headers.items():
            if key in message:
                missing = val
                break
        
        return (
            f"Programming Concept: Libraries and Headers.\n"
            f"Explanation: You are using a standard library feature but forgot to include the header file that defines it.\n"
            f"Fix: Add `#include {missing}` at the top of your file."
        )

    # 3. Access Violation
    if "is private within this context" in message:
        return (
            f"Programming Concept: Encapsulation (Access Modifiers).\n"
            f"Explanation: You are trying to access a 'private' class member from outside the class. Private members are hidden for security/design reasons.\n"
            f"Fix: Use a public getter/setter method to access this variable, or check if you really need needed to access it directly."
        )

    # 4. Const Violation
    if "assignment of read-only variable" in message:
        return (
            f"Programming Concept: Constants.\n"
            f"Explanation: You declared a variable as 'const' (constant), meaning it cannot be changed, but then you tried to change it.\n"
            f"Fix: Remove 'const' from the declaration if you need to change it, or don't assign a new value to it."
        )

    # 5. Signature Mismatch
    if "too few arguments" in message or "too many arguments" in message or "no matching function for call" in message:
        return (
            f"Programming Concept: Function Signatures.\n"
            f"Explanation: You are calling a function with the wrong number or type of arguments.\n"
            f"Fix: Check the function definition and ensure you are passing the correct parameters in the correct order."
        )

    # Fallback for unknown errors
    return (
        f"Programming Concept: General Error.\n"
        f"Explanation: The compiler found an issue: {message}\n"
        f"Fix: Check line {error_info['line']} carefully."
    )
