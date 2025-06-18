# Copyright (C) 2025 SharmaG-omics
#
# Variantis Production is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <https://www.gnu.org/licenses/>.





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
    