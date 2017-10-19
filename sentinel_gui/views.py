
# std lib
import logging

# 3rd parties
from flask import render_template, flash, redirect, url_for

# local
from sentinel_gui.web import app, socketio, sentinel_manager
from sentinel_gui.forms import AddNodeForm

logger = logging.getLogger('sentinel_gui')


@app.route('/', methods=['GET', 'POST'])
@app.route('/index', methods=['GET', 'POST'])
def index():

    form = AddNodeForm()
    if form.validate_on_submit():
        try:
            if sentinel_manager.add_sentinel_node(host=form.host.data, port=form.port.data):
                flash('Adding sentinel {0}:{1} from user request'.format(form.host.data, form.port.data))
            else:
                flash('Adding sentinel {0}:{1} failed'.format(form.host.data, form.port.data))
        except:
            flash('Adding sentinel {0}:{1} failed'.format(form.host.data, form.port.data))
            raise

    return render_template('index.html', form=form, title='Home')


@app.route('/refresh', methods=['POST'])
def refresh():
    return render_template('masters_data.html', title='Home', manager=sentinel_manager)


@app.route('/update')
def update():
    sentinel_manager.update()
    return redirect(url_for('index'))


@app.route('/reset')
def reset():
    sentinel_manager.reset()

    return redirect(url_for('index'))


# Websocket
@socketio.on('connect', namespace='/test')
def on_connect():
    logger.debug("Received WS connection")
