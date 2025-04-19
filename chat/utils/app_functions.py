def app_functions(function_name, function_args):
    """
    Return a list of all the functions that can be called by the AI
    """
    print(f"Function name: {function_name}")
    print(f"Function args: {function_args}")

    if function_name == "extract_features":
        return extract_features(function_args)
    elif function_name == "extract_personas":
        return extract_personas(function_args)

    return None

def extract_features(features):
    """
    Extract the features from the project into a different list
    """
    print("Feature extraction function called \n\n")
    return "Features extracted. Please continue"

def extract_personas(personas):
    """
    Extract the personas from the project into a different list
    """
    print("Persona extraction function called \n\n")
    return "Personas extracted. Please continue"

