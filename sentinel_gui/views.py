
# std lib
import logging

# 3rd parties
from flask import render_template, flash, redirect, url_for
from flask_wtf import FlaskForm
from wtforms import StringField, IntegerField
from wtforms.validators import DataRequired

# local
from sentinel_gui.web import app, sentinel_manager

logger = logging.getLogger('sentinel_gui')


class AddNodeForm(FlaskForm):
    fields = {"class": "form-control mb-2 mr-sm-2 mb-sm-0",
              "placeholder": "sentinel_hostname",
              }
    host = StringField('Sentinel host', id='input_sentinel_host', validators=[DataRequired()], render_kw=fields)
    port = IntegerField('Sentinel post', default=26379, validators=[DataRequired()], render_kw=fields)


@app.route('/', methods=['GET', 'POST'])
@app.route('/index', methods=['GET', 'POST'])
def index():

    form = AddNodeForm()
    if form.validate_on_submit():
        try:
            sentinel_manager.add_sentinel_node(host=form.host.data, port=form.port.data)
            flash('Adding sentinel {0}:{1} from user request'.format(form.host.data, form.port.data))
        except:
            flash('Adding sentinel {0}:{1} failed'.format(form.host.data, form.port.data))

    return render_template('index.html', form=form, title='Home')


@app.route('/refresh', methods=['POST'])
def refresh():

    return render_template('masters_data.html', title='Home', manager=sentinel_manager)


@app.route('/reset')
def reset():
    sentinel_manager.reset()

    return redirect(url_for('index'))
