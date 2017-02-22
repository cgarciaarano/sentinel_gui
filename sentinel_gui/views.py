
from flask import render_template
from flask import jsonify
from sentinel_gui.web import app, sentinel_manager


@app.route('/')
@app.route('/index')
def index():
    sentinel_masters = sentinel_manager.get_masters()

    return render_template('index.html', title='Home', masters=sentinel_masters)


@app.route('/update', methods=['POST'])
def update():
    sentinel_masters = sentinel_manager.get_masters()

    return jsonify({'masters': sentinel_masters})
