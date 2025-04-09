from projects.models import Project, ProjectFeature, ProjectPersona
import json

def app_functions(function_name, function_args, project_id):
    """
    Return a list of all the functions that can be called by the AI
    """
    print(f"Function name: {function_name}")
    print(f"Function args: {function_args}")

    if function_name == "extract_features":
        return extract_features(function_args, project_id)
    elif function_name == "extract_personas":
        return extract_personas(function_args, project_id)
    elif function_name == "get_features":
        return get_features(project_id)
    elif function_name == "get_personas":
        return get_personas(project_id)

    return None

def extract_features(function_args, project_id):
    """
    Extract the features from the project into a different list and save them to the database
    """
    print("Feature extraction function called \n\n")
    
    if project_id is None:
        return json.dumps({
            "notify_frontend": False,
            "message_to_agent": "Error: project_id is required to save features"
        })
    
    try:
        project = Project.objects.get(id=project_id)
    except Project.DoesNotExist:
        return json.dumps({
            "notify_frontend": False,
            "message_to_agent": f"Error: Project with ID {project_id} does not exist"
        })
    
    features = function_args.get('features', [])
    
    try:
        # Delete existing features for this project
        # ProjectFeature.objects.filter(project=project).delete()
        
        # Create new features
        for feature in features:
            new_feature = ProjectFeature(
                project=project,
                name=feature['name'],
                description=feature['description'],
                details=feature['details'],
                priority=feature['priority']
            )
            new_feature.save()
        
        return json.dumps({
            "notify_frontend": True,
            "message_to_agent": f"Features extracted and saved"
        })
    except Exception as e:
        print(f"Error saving features: {str(e)}")
        return json.dumps({
            "notify_frontend": False,
            "message_to_agent": f"Error saving features: {str(e)}"
        })

def extract_personas(function_args, project_id):
    """
    Extract the personas from the project into a different list and save them to the database
    """
    print("Persona extraction function called \n\n")
    
    if project_id is None:
        return json.dumps({
            "notify_frontend": False,
            "message_to_agent": "Error: project_id is required to save personas"
        })
    
    try:
        project = Project.objects.get(id=project_id)
    except Project.DoesNotExist:
        return json.dumps({
            "notify_frontend": False,
            "message_to_agent": f"Error: Project with ID {project_id} does not exist"
        })
    
    personas = function_args.get('personas', [])
    
    try:
        # Delete existing personas for this project
        ProjectPersona.objects.filter(project=project).delete()
        
        # Create new personas
        for persona in personas:
            new_persona = ProjectPersona(
                project=project,
                name=persona['name'],
                role=persona['role'],
                description=persona['description']
            )
            new_persona.save()
        
        return json.dumps({
            "notify_frontend": True,
            "message_to_agent": f"Personas extracted and saved"
        })
    except Exception as e:
        print(f"Error saving personas: {str(e)}")
        return json.dumps({
            "notify_frontend": False,
            "message_to_agent": f"Error saving personas: {str(e)}"
        })

def get_features(project_id):
    """
    Retrieve existing features for a project
    """
    print("Get features function called \n\n")
    
    if project_id is None:
        return "Error: project_id is required to retrieve features"
    
    try:
        project = Project.objects.get(id=project_id)
    except Project.DoesNotExist:
        return f"Error: Project with ID {project_id} does not exist"
    
    features = ProjectFeature.objects.filter(project=project)
    
    if not features.exists():
        return {"features": [], "message": "No features found for this project"}
    
    feature_list = []
    for feature in features:
        feature_list.append({
            "name": feature.name,
            "description": feature.description,
            "details": feature.details,
            "priority": feature.priority
        })
    
    return {"features": feature_list, "message": f"Found {len(feature_list)} features for project {project.name}"}

def get_personas(project_id):
    """
    Retrieve existing personas for a project
    """
    print("Get personas function called \n\n")
    
    if project_id is None:
        return "Error: project_id is required to retrieve personas"
    
    try:
        project = Project.objects.get(id=project_id)
    except Project.DoesNotExist:
        return f"Error: Project with ID {project_id} does not exist"
    
    personas = ProjectPersona.objects.filter(project=project)
    
    if not personas.exists():
        return {"personas": [], "message": "No personas found for this project"}
    
    persona_list = []
    for persona in personas:
        persona_list.append({
            "name": persona.name,
            "role": persona.role,
            "description": persona.description
        })
    
    return {"personas": persona_list, "message": f"Found {len(persona_list)} personas for project {project.name}"}

