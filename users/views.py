from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from .forms import UserRegisterForm, UserUpdateForm, ProfileUpdateForm
from django.contrib.auth.forms import AuthenticationForm

def register(request):
    if request.method == 'POST':
        form = UserRegisterForm(request.POST)
        if form.is_valid():
            form.save()
            username = form.cleaned_data.get('username')
            messages.success(request, f'Account created for {username}! You can now log in.')
            return redirect('login')
    else:
        form = UserRegisterForm()
    return render(request, 'users/auth.html', {'form': form})

def auth(request):
    """
    Combined login and registration view that renders the tabbed auth page.
    This view handles both GET requests (displaying the form) and POST requests
    (processing form submissions) for both login and registration.
    """
    # Initialize both forms
    login_form = AuthenticationForm()
    register_form = UserRegisterForm()
    
    # Determine which form was submitted based on a hidden input field
    if request.method == 'POST':
        form_type = request.POST.get('form_type')
        
        if form_type == 'login':
            login_form = AuthenticationForm(data=request.POST)
            if login_form.is_valid():
                from django.contrib.auth import login
                user = login_form.get_user()
                login(request, user)
                messages.success(request, f'Welcome back, {user.username}!')
                # Redirect to the next parameter if provided, otherwise to home
                next_url = request.GET.get('next', 'profile')
                return redirect(next_url)
        
        elif form_type == 'register':
            register_form = UserRegisterForm(request.POST)
            if register_form.is_valid():
                register_form.save()
                username = register_form.cleaned_data.get('username')
                messages.success(request, f'Account created for {username}! You can now log in.')
                return redirect('login')
    
    # Render the template with both forms
    context = {
        'login_form': login_form,
        'register_form': register_form,
        'active_tab': 'login' if request.method == 'GET' or (request.method == 'POST' and request.POST.get('form_type') == 'login') else 'register'
    }
    return render(request, 'users/auth.html', context)

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
    return render(request, 'users/profile.html', context) 