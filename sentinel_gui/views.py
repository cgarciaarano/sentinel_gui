
# std lib

# 3rd parties
from flask import render_template
#from flask import jsonify

# local
from sentinel_gui.web import app, sentinel_manager


@app.route('/')
@app.route('/index')
def index():
    return render_template('index.html', title='Home')


@app.route('/update', methods=['POST'])
def update():
    sentinel_manager.update()

    return render_template('masters_data.html', title='Home', manager=sentinel_manager)
