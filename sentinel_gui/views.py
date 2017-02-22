
from flask import render_template
from sentinel_gui.web import app, sentinel_manager


@app.route('/')
@app.route('/index')
def index():
    sentinel_masters = sentinel_manager.get_masters()
    
    return render_template('index.html', title='Home', masters=sentinel_masters)
