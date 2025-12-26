"""Web Task GUI for Jarvis using Flask."""

import json
from datetime import datetime
from flask import Flask, render_template, request, jsonify, redirect, url_for
import sys
from pathlib import Path

# Add the project root to Python path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from core import task_manager

app = Flask(__name__)

@app.route('/')
def index():
    """Main task management page."""
    tm = task_manager.get_task_manager()
    tasks = tm.list_tasks(limit=50)
    stats = tm.get_stats()
    
    return render_template('index.html', tasks=tasks, stats=stats)

@app.route('/api/tasks', methods=['GET'])
def api_get_tasks():
    """Get all tasks as JSON."""
    tm = task_manager.get_task_manager()
    status_filter = request.args.get('status')
    priority_filter = request.args.get('priority')
    
    if status_filter:
        status_filter = task_manager.TaskStatus(status_filter)
    if priority_filter:
        priority_filter = task_manager.TaskPriority(priority_filter)
    
    tasks = tm.list_tasks(status=status_filter, priority=priority_filter, limit=100)
    
    return jsonify([{
        'id': task.id,
        'title': task.title,
        'priority': task.priority.value,
        'status': task.status.value,
        'created_at': task.created_at,
        'completed_at': task.completed_at,
        'created_str': datetime.fromtimestamp(task.created_at).strftime("%Y-%m-%d %H:%M")
    } for task in tasks])

@app.route('/api/tasks', methods=['POST'])
def api_add_task():
    """Add a new task."""
    data = request.get_json()
    
    if not data or 'title' not in data:
        return jsonify({'error': 'Title is required'}), 400
    
    priority = data.get('priority', 'medium')
    priority = task_manager.TaskPriority(priority)
    
    tm = task_manager.get_task_manager()
    task = tm.add_task(data['title'], priority)
    
    return jsonify({
        'id': task.id,
        'title': task.title,
        'priority': task.priority.value,
        'status': task.status.value,
        'created_at': task.created_at
    }), 201

@app.route('/api/tasks/<task_id>/start', methods=['POST'])
def api_start_task(task_id):
    """Start a task."""
    tm = task_manager.get_task_manager()
    
    if tm.start_task(task_id):
        return jsonify({'success': True})
    else:
        return jsonify({'error': 'Task not found'}), 404

@app.route('/api/tasks/<task_id>/complete', methods=['POST'])
def api_complete_task(task_id):
    """Complete a task."""
    tm = task_manager.get_task_manager()
    
    if tm.complete_task(task_id):
        return jsonify({'success': True})
    else:
        return jsonify({'error': 'Task not found'}), 404

@app.route('/api/stats')
def api_get_stats():
    """Get task statistics."""
    tm = task_manager.get_task_manager()
    stats = tm.get_stats()
    return jsonify(stats)

if __name__ == '__main__':
    # Create templates directory
    templates_dir = ROOT / "web" / "templates"
    templates_dir.mkdir(parents=True, exist_ok=True)
    
    app.run(host='127.0.0.1', port=5000, debug=True)
