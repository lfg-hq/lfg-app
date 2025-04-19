save_prd = {
    "type": "function",
    "function": 
        {
            "name": "save_prd",
            "description": "Summarize the project based on the provided requirements and save the PRD in Markdown format. This could be an updated PRD either",
            "parameters": {
                "type": "object",
                "properties": {
                    "prd": {
                        "type": "string",
                        "description": "A detailed project PRD in markdown format or the update version of the existing PRD"
                    }
                },
                "required": ["prd"],
                "additionalProperties": False,
            }
        }
}

get_prd = {
    "type": "function",
    "function": {
        "name": "get_prd",
        "description": "Call this function to check if PRD already exists. If it does, it will return the PRD",
    }
}

save_features = {
    "type": "function",
    "function": {
        "name": "save_features",
        "description": "Call this function to save the features from the PRD into a different list",
    }
}

save_personas = {
    "type": "function",
    "function": {
        "name": "save_personas",
        "description": "Call this function to save the personas from the PRD into a different list",
    }
}

extract_features = {
    "type": "function",
    "function": {
        "name": "extract_features",
        "description": "Call this function to extract the features from the project into a different list",
        "parameters": {
            "type": "object",
            "properties": {
                "features": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"},
                            "description": {"type": "string", "description": "A short description of this feature"},
                            "details": {"type": "string", "description": "You will provide a detailed description with at least 3-4 lines"},
                            "priority": {"type": "string", "enum": ["High", "Medium", "Low"]}
                        },
                        "required": ["name", "description", "details", "priority"]
                    }
                }
            },
            "required": ["features"]
        }
    }
}
    
get_features = {
        "type": "function",
        "function":
            {
                "name": "get_features",
                "description": "Call this function to check if Features already exist. If they do, it will return the list of features",
            }
    }

get_personas = {
        "type": "function",
        "function":
            {
                "name": "get_personas",
                "description": "Call this function to check if Personas already exist. If they do, it will return the list of personas",
            }
    }

extract_personas = {
    "type": "function",
    "function": {
        "name": "extract_personas",
        "description": "Call this function to extract the Personas",
        "parameters": {
            "type": "object",
            "properties": {
                "personas": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"},
                            "role": {"type": "string"},
                            "description": {"type": "string"}
                        },
                        "required": ["name", "role", "description"]
                    }
                }
            },
            "required": ["personas"]
        }
    }
}

design_schema = {
    "type": "function",
    "function": {
        "name": "design_schema",
        "description": "Call this function with the detailed design schema for the project",
        "parameters": {
                "type": "object",
                "properties": {
                    "user_input": {
                        "type": "string",
                        "description": "This includes the design request provided by user, whether it is related to colors or fonts, etc."
                    }
                },
                "required": ["user_input"],
                "additionalProperties": False,
        }
    }
}

generate_tickets = {
    "type": "function",
    "function": {
        "name": "generate_tickets",
        "description": "Call this function to generate the tickets for the project",
    }
}

tools = [save_prd, get_prd, save_features, save_personas, design_schema, generate_tickets]