
from flask import render_template
from flask import jsonify
from sentinel_gui.web import app, sentinel_manager


@app.route('/')
@app.route('/index')
def index():
    return render_template('index.html', title='Home', manager=sentinel_manager.serialize())


@app.route('/update', methods=['POST'])
def update():
    sentinel_manager.update()

    return jsonify(sentinel_manager.serialize())
