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
        "parameters": {
            "type": "object",
            "properties": {}
        }
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
        "parameters": {
            "type": "object",
            "properties": {}
        }
    }
}

generate_code = {
    "type": "function",
    "function": {
        "name": "generate_code",
        "description": "Call this function to generate the code based on the user input",
        "parameters": {
            "type": "object",
            "properties": {
                "user_input": {
                    "type": "string",
                    "description": "This includes the code request provided by user, it could be related to building features, projects, fixing bugs, or analysing data"
                }
            },
            "required": ["user_input"],
            "additionalProperties": False,
        }
    }
}

write_code_file = {
    "type": "function",
    "function": {
        "name": "write_code_file",
        "description": "Write the source code files to app directory. This includes file path and the source-code in patch-diff mode for the files sent.",
        "parameters": {
            "type": "object",
            "properties": {
                "files": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "file_path": {"type": "string", "description": "The path of the file to write to"},
                            "source_code": {"type": "string", "description": "The source code of the file in patch-diff mode"},
                        },
                        "required": ["file_path", "source_code"]
                    }
                }
            },
            "required": ["files"]
        }
    }
}

read_code_file = {
    "type": "function",
    "function": {
        "name": "read_code_file",
        "description": "Read the source code files from app directory. This includes file path",
        "parameters": {
            "type": "object",
            "properties": {
                "file_path": {"type": "string", "description": "The path of the file to read from"},
            },
            "required": ["file_path"]
        }
    }
}

execute_command = {
    "type": "function",
    "function": {
        "name": "execute_command",
        "description": "The command that needs to be executed in the terminal. This includes either the command to fetch files, file directory tree, write code via git patch, execute commands, etc. ",
        "parameters": {
            "type": "object",
            "properties": {
                "commands": {"type": "string", "description": "The command that needs to be executed."},
            },
            "required": ["commands"]
        }
    }
}

start_server = {
    "type": "function",
    "function": {
        "name": "start_server",
        "description": "Start the server at port 8000 for backend applications or 3000 for frontend applications. Install dependencies if needed.",
        "parameters": {
            "type": "object",
            "properties": {
                "application_port": {"type": "integer", "description": "The port number at which the application is being run"},
                "type": {"type": "string", "enum": ["backend", "frontend", "background"], "description": "The type of the service to start (backend, frontend, background worker)"},
                "start_server_command": {"type": "string", "description": "The command to run the server, or install dependencies, etc."}
            },
            "required": ["container_port", "start_server_command"]
        }
    }
}

# tools = [save_prd, get_prd, save_features, save_personas, design_schema, generate_tickets, write_code_file, read_code_file]

tools = [execute_command, start_server]