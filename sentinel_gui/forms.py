
# std lib

# 3rd parties
from flask_wtf import FlaskForm
from wtforms import StringField, IntegerField
from wtforms.validators import DataRequired

# local


class AddNodeForm(FlaskForm):
    fields = {"class": "form-control mb-2 mr-sm-2 mb-sm-0",
              "placeholder": "sentinel_hostname",
              }
    host = StringField('Sentinel host', id='input_sentinel_host', validators=[DataRequired()], render_kw=fields)
    port = IntegerField('Sentinel post', default=26379, validators=[DataRequired()], render_kw=fields)
