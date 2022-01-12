from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField, PasswordField, SelectField
from wtforms.validators import DataRequired, Email


TIMES = [
    ('5', '5:00 a.m.'),
    ('6', '6:00 a.m.'),
    ('7', '7:00 a.m.'),
    ('8', '8:00 a.m.'),
    ('9', '9:00 a.m.'),
    ('10', '10:00 a.m.'),
]


class SignupForm(FlaskForm):
    email = StringField("Email", validators=[DataRequired(), Email()])
    password = PasswordField("Password", validators=[DataRequired()])
    submit = SubmitField("Sign Up or Log In!")


class LocationForm(FlaskForm):
    location = StringField("Location Name", validators=[DataRequired()])
    alert_time = SelectField("Alert Time", choices=TIMES)
    submit = SubmitField("Add Alert")
