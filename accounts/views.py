from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.urls import reverse
from django.contrib.auth import authenticate, login
from .forms import UserRegisterForm, UserUpdateForm, ProfileUpdateForm, EmailAuthenticationForm
from django.contrib.auth.models import User

def register(request):
    if request.method == 'POST':
        form = UserRegisterForm(request.POST)
        if form.is_valid():
            form.save()
            email = form.cleaned_data.get('email')
            messages.success(request, f'Account created for {email}! You can now log in.')
            return redirect('login')
    else:
        form = UserRegisterForm()
    return render(request, 'accounts/auth.html', {'form': form, 'active_tab': 'register'})

def auth(request):
    """
    Combined login and registration view that renders the tabbed auth page.
    This view handles both GET requests (displaying the form) and POST requests
    (processing form submissions) for both login and registration.
    """
    # Initialize both forms
    login_form = EmailAuthenticationForm()
    register_form = UserRegisterForm()
    
    # Determine which form was submitted based on a hidden input field
    if request.method == 'POST':
        form_type = request.POST.get('form_type')
        
        if form_type == 'login':
            login_form = EmailAuthenticationForm(request, data=request.POST)
            if login_form.is_valid():
                user = login_form.get_user()
                login(request, user)
                messages.success(request, f'Welcome back!')
                
                # Redirect to the chat page or next parameter if provided
                next_url = request.GET.get('next')
                if next_url:
                    return redirect(next_url)
                return redirect('/chat/')  # Direct URL is more reliable here
        
        elif form_type == 'register':
            register_form = UserRegisterForm(request.POST)
            if register_form.is_valid():
                register_form.save()
                email = register_form.cleaned_data.get('email')
                messages.success(request, f'Account created for {email}! You can now log in.')
                return redirect('login')
    
    # Render the template with both forms
    context = {
        'login_form': login_form,
        'register_form': register_form,
        'active_tab': 'login' if request.method == 'GET' or (request.method == 'POST' and request.POST.get('form_type') == 'login') else 'register'
    }
    return render(request, 'accounts/auth.html', context)

@login_required
def profile(request):
    if request.method == 'POST':
        u_form = UserUpdateForm(request.POST, instance=request.user)
        p_form = ProfileUpdateForm(request.POST, request.FILES, instance=request.user.profile)
        
        if u_form.is_valid() and p_form.is_valid():
            u_form.save()
            p_form.save()
            messages.success(request, f'Your account has been updated!')
            return redirect('profile')
    else:
        u_form = UserUpdateForm(instance=request.user)
        p_form = ProfileUpdateForm(instance=request.user.profile)
        
    context = {
        'u_form': u_form,
        'p_form': p_form
    }
    return render(request, 'accounts/profile.html', context) 