#app/routes/main.py
from flask import Blueprint, render_template, redirect, url_for,request

main_bp = Blueprint('main', __name__)

@main_bp.route('/')
@main_bp.route('/home')
def home():
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return render_template('home.html')
    
    return render_template('home.html')

@main_bp.route('/tutorial') 
def tutorial_section():
        # Check if it's an AJAX request
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return render_template('tutorial.html')
    return render_template('home.html')
    

@main_bp.route('/example') 
def example_section():
        # Check if it's an AJAX request
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return render_template('example.html')
    return render_template('home.html')
    

@main_bp.route('/about') 
def about_section():
        # Check if it's an AJAX request
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return render_template('about.html')
    return render_template('home.html')
    