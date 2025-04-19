from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.contrib import messages
from .models import Project, ProjectFeature, ProjectPersona, ProjectPRD, ProjectDesignSchema, ProjectTickets
from django.views.decorators.http import require_POST

# Create your views here.

@login_required
def project_list(request):
    """View to display all projects for the current user"""
    projects = Project.objects.filter(owner=request.user).order_by('-created_at')
    return render(request, 'projects/project_list.html', {
        'projects': projects
    })

@login_required
def project_detail(request, project_id):
    """View to display a specific project"""
    project = get_object_or_404(Project, id=project_id, owner=request.user)
    print(project.direct_conversations.all())
    return render(request, 'projects/project_detail.html', {
        'project': project
    })

@login_required
def create_project(request):
    """View to create a new project"""
    if request.method == 'POST':
        name = request.POST.get('name')
        description = request.POST.get('description')
        icon = request.POST.get('icon', '📋')
        
        if not name:
            messages.error(request, "Project name is required")
            return redirect('create_project')
        
        project = Project.objects.create(
            name=name,
            description=description,
            icon=icon,
            owner=request.user
        )
        
        messages.success(request, f"Project '{name}' created successfully!")
        
        # Redirect to create a conversation for this project
        return redirect('create_conversation', project_id=project.id)
    
    return render(request, 'projects/create_project.html')

@login_required
def update_project(request, project_id):
    """View to update a project"""
    project = get_object_or_404(Project, id=project_id, owner=request.user)
    
    if request.method == 'POST':
        project.name = request.POST.get('name', project.name)
        project.description = request.POST.get('description', project.description)
        project.icon = request.POST.get('icon', project.icon)
        project.status = request.POST.get('status', project.status)
        project.save()
        
        messages.success(request, "Project updated successfully!")
        return redirect('project_detail', project_id=project.id)
    
    # For GET requests, render the update form
    return render(request, 'projects/update_project.html', {
        'project': project
    })

@login_required
@require_POST
def delete_project(request, project_id):
    """View to delete a project"""
    project = get_object_or_404(Project, id=project_id, owner=request.user)
    project_name = project.name
    project.delete()
    
    messages.success(request, f"Project '{project_name}' deleted successfully")
    return redirect('project_list')

@login_required
def project_features_api(request, project_id):
    """API view to get features for a project"""
    project = get_object_or_404(Project, id=project_id, owner=request.user)
    features = ProjectFeature.objects.filter(project=project).order_by('-created_at')
    
    features_list = []
    for feature in features:
        features_list.append({
            'id': feature.id,
            'name': feature.name,
            'description': feature.description,
            'details': feature.details,
            'priority': feature.priority
        })
    
    return JsonResponse({'features': features_list})

@login_required
def project_personas_api(request, project_id):
    """API view to get personas for a project"""
    project = get_object_or_404(Project, id=project_id, owner=request.user)
    personas = ProjectPersona.objects.filter(project=project).order_by('-created_at')
    
    personas_list = []
    for persona in personas:
        personas_list.append({
            'id': persona.id,
            'name': persona.name,
            'role': persona.role,
            'description': persona.description
        })
    
    return JsonResponse({'personas': personas_list})

@login_required
def project_prd_api(request, project_id):
    """API view to get PRD for a project"""
    project = get_object_or_404(Project, id=project_id, owner=request.user)
    
    # Get the PRD or create it if it doesn't exist
    prd, created = ProjectPRD.objects.get_or_create(
        project=project,
        defaults={'prd': ''}  # Default empty content if we're creating a new PRD
    )
    
    # Convert to JSON-serializable format
    prd_data = {
        'id': prd.id,
        'content': prd.prd,
        'title': 'Product Requirement Document',
        'updated_at': prd.updated_at.strftime('%Y-%m-%d %H:%M') if prd.updated_at else None
    }
    
    return JsonResponse(prd_data)   

@login_required
def project_design_schema_api(request, project_id):
    """API view to get design schema for a project"""
    project = get_object_or_404(Project, id=project_id, owner=request.user)
    
    # Get the design schema or create it if it doesn't exist
    design_schema, created = ProjectDesignSchema.objects.get_or_create(
        project=project,
        defaults={'design_schema': ''}  # Default empty content if we're creating a new design schema
    )
    
    # Convert to JSON-serializable format
    design_schema_data = {
        'id': design_schema.id,
        'content': design_schema.design_schema,
        'title': 'Design Schema',
        'updated_at': design_schema.updated_at.strftime('%Y-%m-%d %H:%M') if design_schema.updated_at else None
    }
    
    return JsonResponse(design_schema_data)

@login_required
def project_tickets_api(request, project_id):
    """API view to get tickets for a project, including feature information"""
    project = get_object_or_404(Project, id=project_id, owner=request.user)
    
    # Get all tickets for this project
    tickets = ProjectTickets.objects.filter(project=project).select_related('feature')
    
    tickets_list = []
    for ticket in tickets:
        tickets_list.append({
            'id': ticket.id,
            'ticket_id': ticket.ticket_id,
            'title': ticket.title,
            'description': ticket.description,
            'status': ticket.status,
            'feature': {
                'id': ticket.feature.id,
                'name': ticket.feature.name,
                'priority': ticket.feature.priority
            },
            'backend_tasks': ticket.backend_tasks,
            'frontend_tasks': ticket.frontend_tasks,
            'implementation_steps': ticket.implementation_steps,
            'created_at': ticket.created_at.isoformat(),
            'updated_at': ticket.updated_at.isoformat(),
        })
    
    return JsonResponse({'tickets': tickets_list})

